import hashlib
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver
from django.utils import timezone

from .models import (
    EstoqueSaldo,
    LogAuditoriaEstoque,
    MovimentoEstoque,
    PedidoSeparacao,
    PedidoSeparacaoAnexo,
    PedidoSeparacaoItem,
    PedidoSeparacaoMensagem,
)

# -----------------------------
# Sinais de domínio (custom Signals para extensões futuras)
# -----------------------------
movimento_registrado = Signal()  # args: movimento, acao
reserva_criada = Signal()  # args: reserva
reserva_consumida = Signal()  # args: reserva
pedido_picking_criado = Signal()  # args: pedido
pedido_picking_status = Signal()  # args: pedido, status_anterior, status_novo

# ------------------------------------------------------------------
# Handlers Django signals (model pre_save / post_save) + broadcasts
# Migrados de signals_novos.py para unificação
# ------------------------------------------------------------------


# ---------- Código automático PedidoSeparacao ----------
@receiver(pre_save, sender=PedidoSeparacao)
def pedido_separacao_codigo(sender, instance: PedidoSeparacao, **kwargs):
    if not instance.codigo:
        instance.codigo = f"PS-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


# ---------- Contadores PedidoSeparacao ----------
@receiver(post_save, sender=PedidoSeparacaoItem)
def atualizar_contadores_pedido(sender, instance: PedidoSeparacaoItem, **kwargs):
    pedido = instance.pedido
    itens = pedido.itens.all()
    pedido.itens_totais = itens.count()
    pedido.itens_separados = itens.filter(status_item="SEPARADO").count()
    pedido.itens_pendentes = itens.filter(status_item="PENDENTE").count()
    pedido.save(update_fields=["itens_totais", "itens_pendentes", "itens_separados", "atualizado_em"])
    _broadcast_picking(
        {
            "event": "pedido.item.atualizado",
            "pedido_id": pedido.id,
            "item_id": instance.id,
            "status_item": instance.status_item,
            "itens_pendentes": pedido.itens_pendentes,
            "itens_separados": pedido.itens_separados,
        }
    )


# ---------- Anexos count ----------
@receiver(post_save, sender=PedidoSeparacaoAnexo)
def atualizar_anexos_count(sender, instance: PedidoSeparacaoAnexo, **kwargs):
    mensagem = instance.mensagem
    count = mensagem.anexos.count()
    if mensagem.anexos_count != count:
        mensagem.anexos_count = count
        mensagem.save(update_fields=["anexos_count"])
    _broadcast_picking(
        {
            "event": "pedido.mensagem.anexo",
            "pedido_id": mensagem.pedido_id,
            "mensagem_id": mensagem.id,
            "anexos_count": mensagem.anexos_count,
        }
    )


# ---------- Auditoria MovimentoEstoque ----------
@receiver(post_save, sender=MovimentoEstoque)
def auditar_movimento(sender, instance: MovimentoEstoque, created, **kwargs):
    if not created:
        return
    previous = LogAuditoriaEstoque.objects.order_by("-id").first()

    snapshot_antes = None
    if instance.metadata and isinstance(instance.metadata, dict) and "snapshot_antes" in instance.metadata:
        snapshot_antes = instance.metadata.get("snapshot_antes")

    snapshot_depois = {
        "produto_id": instance.produto_id,
        "tipo": instance.tipo,
        "quantidade": str(instance.quantidade),
        "custo_unit": str(instance.custo_unitario_snapshot),
        "deposito_origem": instance.deposito_origem_id,
        "deposito_destino": instance.deposito_destino_id,
        "solicitante_tipo": instance.solicitante_tipo,
        "solicitante_id": instance.solicitante_id,
        "aprovacao_status": instance.aprovacao_status,
        "aplicado": instance.aplicado,
        "valor_estimado": str(instance.valor_estimado),
        "criado_em": instance.criado_em.isoformat(),
    }

    deposito_rel = instance.deposito_origem or instance.deposito_destino
    if deposito_rel and instance.aplicado:
        try:
            saldo = EstoqueSaldo.objects.get(produto=instance.produto, deposito=deposito_rel)
            snapshot_depois["saldo_atual"] = str(saldo.quantidade)
            snapshot_depois["reservado_atual"] = str(saldo.reservado)
        except EstoqueSaldo.DoesNotExist:
            pass

    base_string = (previous.hash_atual if previous else "") + repr(snapshot_depois)
    hash_atual = hashlib.sha256(base_string.encode("utf-8")).hexdigest()
    LogAuditoriaEstoque.objects.create(
        movimento=instance,
        snapshot_antes=snapshot_antes,
        snapshot_depois=snapshot_depois,
        hash_previo=previous.hash_atual if previous else None,
        hash_atual=hash_atual,
        usuario=instance.usuario_executante,
        tenant=instance.tenant,
    )
    _broadcast_estoque(
        {
            "event": "movimento.criado",
            "movimento_id": instance.id,
            "produto_id": instance.produto_id,
            "tipo": instance.tipo,
            "quantidade": str(instance.quantidade),
            "aprovacao_status": instance.aprovacao_status,
            "aplicado": instance.aplicado,
            "tenant_id": instance.tenant_id,
        }
    )


@receiver(post_save, sender=PedidoSeparacao)
def broadcast_pedido_status(sender, instance: PedidoSeparacao, created, **kwargs):
    payload_data = {
        "pedido_id": instance.id,
        "status": instance.status,
        "prioridade": instance.prioridade,
        "tenant_id": instance.tenant_id,
        "codigo": instance.codigo,
    }
    _broadcast_picking(_envelope("picking.pedido" if created else "picking.status", payload_data))


@receiver(post_save, sender=PedidoSeparacaoMensagem)
def broadcast_pedido_mensagem(sender, instance: PedidoSeparacaoMensagem, created, **kwargs):
    if created:
        _broadcast_picking(
            _envelope(
                "picking.mensagem",
                {"pedido_id": instance.pedido_id, "mensagem_id": instance.id, "tenant_id": instance.pedido.tenant_id},
            )
        )


def _envelope(event_name: str, data: dict):
    return {"event": event_name, "ts": timezone.now().isoformat(), "version": 1, "data": data}


def _broadcast_estoque(payload: dict):
    layer = get_channel_layer()
    grupos = ["estoque_stream"]
    tenant_id = payload["data"].get("tenant_id") if isinstance(payload.get("data"), dict) else None
    if tenant_id:
        grupos.append(f"estoque_tenant_{tenant_id}")
    for g in grupos:
        async_to_sync(layer.group_send)(g, {"type": "estoque_event", "data": payload})


def _broadcast_picking(payload: dict):
    layer = get_channel_layer()
    grupos = ["picking_stream"]
    tenant_id = payload["data"].get("tenant_id") if isinstance(payload.get("data"), dict) else None
    if tenant_id:
        grupos.append(f"picking_tenant_{tenant_id}")
    for g in grupos:
        async_to_sync(layer.group_send)(g, {"type": "picking_event", "data": payload})

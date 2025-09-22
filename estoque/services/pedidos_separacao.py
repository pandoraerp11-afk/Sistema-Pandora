import contextlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from estoque.models import (
    PedidoSeparacao,
    PedidoSeparacaoItem,
    PedidoSeparacaoMensagem,
)
from estoque.signals import pedido_picking_criado, pedido_picking_status
from shared.exceptions import NegocioError

from .reservas import ReservaService  # criar_reserva agora via serviço


def _codigo_pedido():
    return f"PS-{timezone.now().strftime('%Y%m%d%H%M%S')}"


@transaction.atomic
def criar_pedido(
    solicitante_tipo: str,
    solicitante_id: str,
    solicitante_nome: str,
    itens: list[dict],
    prioridade="NORMAL",
    criado_por=None,
    permitir_retirada_parcial=False,
    data_limite=None,
    tenant=None,
    max_urgentes=5,
):
    if not itens:
        raise NegocioError("Pedido deve conter ao menos 1 item.")
    if prioridade == "URGENTE":
        urgentes = PedidoSeparacao.objects.filter(
            tenant=tenant, prioridade="URGENTE", status__in=["ABERTO", "EM_PREPARACAO"]
        ).count()
        if urgentes >= max_urgentes:
            raise NegocioError("Limite de pedidos URGENTE ativos atingido.")
    pedido = PedidoSeparacao.objects.create(
        codigo=_codigo_pedido(),
        solicitante_tipo=solicitante_tipo,
        solicitante_id=solicitante_id,
        solicitante_nome_cache=solicitante_nome,
        prioridade=prioridade,
        criado_por_user=criado_por,
        permitir_retirada_parcial=permitir_retirada_parcial,
        data_limite=data_limite,
        tenant=tenant,
    )
    for item in itens:
        PedidoSeparacaoItem.objects.create(
            pedido=pedido,
            produto=item["produto"],
            quantidade_solicitada=item["quantidade"],
            unidade=item.get("unidade"),
            tenant=tenant,
        )
    # contadores via signal
    with contextlib.suppress(Exception):
        pedido_picking_criado.send(sender=PedidoSeparacao, pedido=pedido)
    return pedido


@transaction.atomic
def iniciar_preparacao(pedido: PedidoSeparacao, operador):
    if pedido.status not in ["ABERTO"]:
        raise NegocioError("Pedido não pode iniciar preparação neste status.")
    pedido.status = "EM_PREPARACAO"
    pedido.operador_responsavel = operador
    pedido.inicio_preparo = timezone.now()
    pedido.save(update_fields=["status", "operador_responsavel", "inicio_preparo", "atualizado_em"])
    with contextlib.suppress(Exception):
        pedido_picking_status.send(
            sender=PedidoSeparacao, pedido=pedido, status_anterior="ABERTO", status_novo="EM_PREPARACAO"
        )
    return pedido


@transaction.atomic
def marcar_item_separado(item: PedidoSeparacaoItem, quantidade: Decimal, operador=None):
    if item.status_item not in ["PENDENTE", "PARCIAL"]:
        raise NegocioError("Item não pode ser separado neste status.")
    if item.pedido.status not in ["EM_PREPARACAO"]:
        raise NegocioError("Pedido não está em preparação.")
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    restante = item.quantidade_solicitada - item.quantidade_separada
    if quantidade > restante:
        raise NegocioError("Quantidade excede restante a separar.")
    # Criar reserva se não existir (bloqueio de saldo)
    if not item.deposito:
        raise NegocioError("Item sem depósito definido.")
    if not item.reserva:
        item.reserva = ReservaService.criar_reserva(
            produto_id=item.produto_id,
            deposito_id=item.deposito_id,
            quantidade=quantidade,
            origem_tipo="PICKING",
            origem_id=str(item.pedido_id),
            tenant=item.tenant,
            usuario=operador,
        )
    else:
        # TODO: Implementar aumento de reserva incremental se necessário
        pass
    item.quantidade_separada += quantidade
    if item.quantidade_separada == item.quantidade_solicitada:
        item.status_item = "SEPARADO"
    else:
        item.status_item = "PARCIAL"
    item.save(update_fields=["quantidade_separada", "status_item", "atualizado_em", "reserva"])
    return item


@transaction.atomic
def marcar_item_indisponivel(item: PedidoSeparacaoItem, observacao: str):
    if item.status_item in ["SEPARADO", "INDISPONIVEL"]:
        raise NegocioError("Item já finalizado.")
    if item.pedido.status not in ["EM_PREPARACAO"]:
        raise NegocioError("Pedido não está em preparação.")
    if not observacao or len(observacao) < 10:
        raise NegocioError("Observação mínima de 10 caracteres para indisponível.")
    item.status_item = "INDISPONIVEL"
    item.observacao = observacao
    item.save(update_fields=["status_item", "observacao", "atualizado_em"])
    return item


@transaction.atomic
def concluir_pedido(pedido: PedidoSeparacao):
    itens_pend = pedido.itens.filter(status_item="PENDENTE").exists()
    if itens_pend:
        raise NegocioError("Existem itens pendentes.")
    # Não permitir concluir se algum item PARCIAL e não permitir_retirada_parcial
    if not pedido.permitir_retirada_parcial and pedido.itens.filter(status_item="PARCIAL").exists():
        raise NegocioError("Existem itens parciais e retirada parcial não permitida.")
    pedido.status = "PRONTO"
    pedido.pronto_em = timezone.now()
    pedido.save(update_fields=["status", "pronto_em", "atualizado_em"])
    with contextlib.suppress(Exception):
        pedido_picking_status.send(
            sender=PedidoSeparacao, pedido=pedido, status_anterior="EM_PREPARACAO", status_novo="PRONTO"
        )
    return pedido


@transaction.atomic
def registrar_retirada(pedido: PedidoSeparacao):
    if pedido.status != "PRONTO" and not pedido.permitir_retirada_parcial:
        raise NegocioError("Pedido não está pronto para retirada.")
    if pedido.permitir_retirada_parcial and pedido.status not in ["PRONTO", "EM_PREPARACAO"]:
        raise NegocioError("Status inválido para retirada parcial.")
    pedido.status = "RETIRADO"
    pedido.retirado_em = timezone.now()
    pedido.save(update_fields=["status", "retirado_em", "atualizado_em"])
    with contextlib.suppress(Exception):
        pedido_picking_status.send(
            sender=PedidoSeparacao, pedido=pedido, status_anterior="PRONTO", status_novo="RETIRADO"
        )
    return pedido


@transaction.atomic
def adicionar_mensagem(
    pedido: PedidoSeparacao, texto: str, autor_user=None, autor_tipo=None, autor_id=None, importante=False
):
    if not texto or len(texto.strip()) == 0:
        raise NegocioError("Mensagem vazia.")
    msg = PedidoSeparacaoMensagem.objects.create(
        pedido=pedido,
        autor_user=autor_user,
        autor_tipo=autor_tipo,
        autor_id=autor_id,
        texto=texto.strip(),
        importante=importante,
        tenant=pedido.tenant,
    )
    return msg

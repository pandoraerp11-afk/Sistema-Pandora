import contextlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from estoque.models import Deposito, EstoqueSaldo, Lote, MovimentoEstoque, MovimentoLote
from estoque.services.kpis import invalidar_kpis
from estoque.signals import movimento_registrado
from shared.exceptions import NegocioError, SaldoInsuficienteError


def _saldo_lock(produto, deposito):
    saldo, _ = EstoqueSaldo.objects.select_for_update().get_or_create(produto=produto, deposito=deposito)
    return saldo


@transaction.atomic
def registrar_descarte(
    produto,
    deposito: Deposito,
    quantidade: Decimal,
    usuario,
    justificativa: str,
    tipo="DESCARTE",
    metadata=None,
    threshold_aprovacao_valor: Decimal | None = Decimal("0"),
    tenant=None,
    lotes=None,
    evidencias_ids=None,
    valor_perda_minimo_evidencia=Decimal("0"),
):
    """Registra descarte/perda/vencimento.
    Se valor estimado > threshold_aprovacao_valor cria movimento PENDENTE (aplicado=False) aguardando aprovação.
    Caso contrário aplica impacto imediato.
    """
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    if not justificativa or len(justificativa.strip()) < 15:
        raise NegocioError("Justificativa mínima de 15 caracteres para descarte/perda.")
    if tipo not in ["DESCARTE", "PERDA", "VENCIMENTO"]:
        raise NegocioError("Tipo inválido para descarte.")
    saldo = _saldo_lock(produto, deposito)
    if saldo.quantidade - saldo.reservado < quantidade:
        raise SaldoInsuficienteError(produto.id, deposito.id, quantidade, saldo.quantidade - saldo.reservado)
    lotes_mov = []
    if lotes:
        total = Decimal("0")
        for li in lotes:
            qtd = Decimal(str(li.get("quantidade", "0")))
            if qtd <= 0:
                raise NegocioError("Quantidade de lote inválida.")
            if "id" in li:
                lote = Lote.objects.select_for_update().get(id=li["id"], produto=produto)
            else:
                lote = Lote.objects.select_for_update().get(produto=produto, codigo=li["codigo"])
            if lote.deposito_id and lote.deposito_id != deposito.id:
                raise NegocioError(f"Lote {lote.codigo} não pertence ao depósito.")
            if lote.quantidade_atual - lote.quantidade_reservada < qtd:
                raise NegocioError(f"Lote {lote.codigo} saldo insuficiente.")
            if tipo == "VENCIMENTO" and (not lote.validade or lote.validade > timezone.now().date()):
                raise NegocioError(f"Lote {lote.codigo} não está vencido.")
            lote.quantidade_atual -= qtd
            lote.save(update_fields=["quantidade_atual"])
            lotes_mov.append((lote, qtd))
            total += qtd
        if total != quantidade:
            raise NegocioError("Soma das quantidades dos lotes difere da quantidade total do descarte.")
    valor_perda = saldo.custo_medio * quantidade
    exige_aprovacao = threshold_aprovacao_valor is not None and valor_perda > threshold_aprovacao_valor
    if valor_perda_minimo_evidencia and valor_perda >= valor_perda_minimo_evidencia:
        # exigir evidencias (IDs fornecidos) – checagem simples
        if not evidencias_ids or len(evidencias_ids) == 0:
            raise NegocioError("Evidência obrigatória para perdas acima do limite configurado.")
    snapshot_antes = {
        "saldo_quantidade": str(saldo.quantidade),
        "saldo_reservado": str(saldo.reservado),
    }
    md = metadata or {}
    md["valor_perda_estimado"] = str(valor_perda)
    md["justificativa"] = justificativa
    md["snapshot_antes"] = snapshot_antes
    if evidencias_ids:
        md["evidencias_ids"] = evidencias_ids
    mov = MovimentoEstoque.objects.create(
        produto=produto,
        deposito_origem=deposito,
        tipo=tipo,
        quantidade=quantidade,
        custo_unitario_snapshot=saldo.custo_medio,
        usuario_executante=usuario,
        motivo=justificativa[:250],
        metadata=md,
        aprovacao_status="PENDENTE" if exige_aprovacao else "APROVADO",
        aplicado=not exige_aprovacao,
        valor_estimado=valor_perda,
        tenant=tenant,
    )
    if not exige_aprovacao:
        # aplica imediatamente
        saldo.quantidade -= quantidade
        saldo.save(update_fields=["quantidade", "atualizado_em"])
        for lote, qtd in lotes_mov:
            MovimentoLote.objects.create(movimento=mov, lote=lote, quantidade=qtd)
        try:
            from estoque.services.reabastecimento import avaliar_regras_para_saldo

            avaliar_regras_para_saldo(saldo)
        except Exception:
            pass
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=mov, acao=tipo)
    return mov


@transaction.atomic
def aprovar_movimento_perda(movimento: MovimentoEstoque, aprovador):
    if movimento.tipo not in ["DESCARTE", "PERDA", "VENCIMENTO"]:
        raise NegocioError("Movimento não é perda/descarte.")
    if movimento.aprovacao_status != "PENDENTE":
        raise NegocioError("Movimento não está pendente.")
    if movimento.aplicado:
        raise NegocioError("Movimento já aplicado.")
    saldo = _saldo_lock(movimento.produto, movimento.deposito_origem)
    if saldo.quantidade - saldo.reservado < movimento.quantidade:
        raise SaldoInsuficienteError(
            movimento.produto_id, movimento.deposito_origem_id, movimento.quantidade, saldo.quantidade - saldo.reservado
        )
    saldo.quantidade -= movimento.quantidade
    saldo.save(update_fields=["quantidade", "atualizado_em"])
    movimento.aprovacao_status = "APROVADO"
    movimento.aplicado = True
    from django.utils import timezone

    movimento.aplicado_em = timezone.now()
    md = movimento.metadata or {}
    md["aprovado_por"] = aprovador.id if aprovador else None
    movimento.metadata = md
    movimento.save(update_fields=["aprovacao_status", "aplicado", "aplicado_em", "metadata"])
    try:
        from estoque.services.reabastecimento import avaliar_regras_para_saldo

        avaliar_regras_para_saldo(saldo)
    except Exception:
        pass
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=movimento, acao=f"APROVACAO_{movimento.tipo}")
    invalidar_kpis(movimento.tenant)
    return movimento


@transaction.atomic
def rejeitar_movimento_perda(movimento: MovimentoEstoque, aprovador, motivo_rejeicao: str):
    if movimento.tipo not in ["DESCARTE", "PERDA", "VENCIMENTO"]:
        raise NegocioError("Movimento não é perda/descarte.")
    if movimento.aprovacao_status != "PENDENTE":
        raise NegocioError("Movimento não está pendente.")
    movimento.aprovacao_status = "REJEITADO"
    md = movimento.metadata or {}
    md["rejeitado_por"] = aprovador.id if aprovador else None
    md["motivo_rejeicao"] = motivo_rejeicao
    movimento.metadata = md
    movimento.save(update_fields=["aprovacao_status", "metadata"])
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=movimento, acao=f"REJEICAO_{movimento.tipo}")
    invalidar_kpis(movimento.tenant)
    return movimento

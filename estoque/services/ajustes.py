from decimal import Decimal

from django.db import transaction

from estoque.models import Deposito, EstoqueSaldo, MovimentoEstoque
from shared.exceptions import NegocioError, SaldoInsuficienteError


def _saldo_lock(produto, deposito):
    saldo, _ = EstoqueSaldo.objects.select_for_update().get_or_create(produto=produto, deposito=deposito)
    return saldo


@transaction.atomic
def ajuste_positivo(produto, deposito: Deposito, quantidade: Decimal, usuario, motivo=None, metadata=None):
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    saldo = _saldo_lock(produto, deposito)
    saldo.quantidade += quantidade
    saldo.save(update_fields=["quantidade", "atualizado_em"])
    return MovimentoEstoque.objects.create(
        produto=produto,
        deposito_destino=deposito,
        tipo="AJUSTE_POS",
        quantidade=quantidade,
        custo_unitario_snapshot=saldo.custo_medio,
        usuario_executante=usuario,
        motivo=motivo,
        metadata=metadata or {},
    )


@transaction.atomic
def ajuste_negativo(produto, deposito: Deposito, quantidade: Decimal, usuario, motivo=None, metadata=None):
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    saldo = _saldo_lock(produto, deposito)
    if saldo.quantidade - saldo.reservado < quantidade:
        raise SaldoInsuficienteError(produto.id, deposito.id, quantidade, saldo.quantidade - saldo.reservado)
    saldo.quantidade -= quantidade
    saldo.save(update_fields=["quantidade", "atualizado_em"])
    return MovimentoEstoque.objects.create(
        produto=produto,
        deposito_origem=deposito,
        tipo="AJUSTE_NEG",
        quantidade=quantidade,
        custo_unitario_snapshot=saldo.custo_medio,
        usuario_executante=usuario,
        motivo=motivo,
        metadata=metadata or {},
    )

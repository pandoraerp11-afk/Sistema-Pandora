from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from estoque.models import CamadaCusto, Deposito, EstoqueSaldo
from shared.exceptions import SaldoInsuficienteError

# Valuation FIFO (PEPS) aprimorado.


def is_fifo(produto):
    return getattr(produto, "tipo_custo", None) == "peps"


@transaction.atomic
def registrar_entrada_fifo(
    produto, deposito: Deposito, quantidade: Decimal, custo_unitario: Decimal, tenant=None, merge=True
):
    """Cria (ou agrega) uma camada FIFO.

    merge: se True, e a última camada ainda não foi parcialmente consumida e possui mesmo custo,
    agrega a quantidade para evitar explosão de registros.
    """
    if quantidade <= 0:
        return
    if merge:
        ultima = (
            CamadaCusto.objects.select_for_update()
            .filter(produto=produto, deposito=deposito)
            .order_by("-ordem")
            .first()
        )
        if ultima and ultima.custo_unitario == custo_unitario and ultima.quantidade_restante > 0:
            # agrega
            ultima.quantidade_restante += quantidade
            ultima.save(update_fields=["quantidade_restante"])
            return ultima
    return CamadaCusto.objects.create(
        produto=produto,
        deposito=deposito,
        tenant=tenant,
        quantidade_restante=quantidade,
        custo_unitario=custo_unitario,
    )


@transaction.atomic
def consumir_fifo(produto, deposito: Deposito, quantidade: Decimal):
    """Consome camadas FIFO na ordem. Retorna custo médio ponderado da saída.

    Lança SaldoInsuficienteError se faltar quantidade.
    """
    restante = quantidade
    if quantidade <= 0:
        return Decimal("0")
    camadas = (
        CamadaCusto.objects.select_for_update()
        .filter(produto=produto, deposito=deposito, quantidade_restante__gt=0)
        .order_by("ordem")
    )
    custo_total = Decimal("0")
    for camada in camadas:
        if restante <= 0:
            break
        consumir = min(restante, camada.quantidade_restante)
        if consumir > 0:
            custo_total += consumir * camada.custo_unitario
            camada.quantidade_restante -= consumir
            camada.save(update_fields=["quantidade_restante"])
            restante -= consumir
    if restante > 0:
        raise SaldoInsuficienteError(produto.id, deposito.id, quantidade, quantidade - restante)
    return (custo_total / quantidade).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def reprocessar_valuation(produto, deposito: Deposito):
    """Recalcula custo_medio do saldo a partir das camadas remanescentes.

    Mantém custo_medio coerente para relatórios rápidos (mesmo em PEPS usamos
    custo médio para exibir valor armazenado). Não altera as camadas.
    """
    saldo = EstoqueSaldo.objects.select_for_update().filter(produto=produto, deposito=deposito).first()
    if not saldo:
        return
    camadas = CamadaCusto.objects.filter(produto=produto, deposito=deposito, quantidade_restante__gt=0)
    total_qtd = sum(c.quantidade_restante for c in camadas)
    if total_qtd == 0:
        saldo.custo_medio = 0
        saldo.save(update_fields=["custo_medio", "atualizado_em"])
        return Decimal("0")
    total_valor = sum(c.quantidade_restante * c.custo_unitario for c in camadas)
    novo_custo = (total_valor / total_qtd).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    if saldo.custo_medio != novo_custo:
        saldo.custo_medio = novo_custo
        saldo.save(update_fields=["custo_medio", "atualizado_em"])
    return saldo.custo_medio


def registrar_entrada_fifo_e_atualizar(produto, deposito, quantidade, custo_unitario, tenant=None):
    registrar_entrada_fifo(produto, deposito, quantidade, custo_unitario, tenant=tenant)
    # Atualiza custo médio representativo das camadas
    reprocessar_valuation(produto, deposito)


def consumir_fifo_e_atualizar(produto, deposito, quantidade):
    custo = consumir_fifo(produto, deposito, quantidade)
    reprocessar_valuation(produto, deposito)
    return custo

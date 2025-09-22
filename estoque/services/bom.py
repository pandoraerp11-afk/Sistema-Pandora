import contextlib
from decimal import Decimal

from django.db import transaction

from estoque.models import Deposito, EstoqueSaldo, MovimentoEstoque
from estoque.services.kpis import invalidar_kpis
from estoque.signals import movimento_registrado
from produtos.models import ProdutoBOMItem
from shared.exceptions import NegocioError, SaldoInsuficienteError

"""Serviço de consumo de BOM (Bill of Materials).
Assume existência de uma estrutura externa que define componentes de um produto pai.
Interface esperada: obter_componentes(produto) -> lista de dict {componente, quantidade_por_unidade}
"""


def obter_componentes(produto):
    itens = ProdutoBOMItem.objects.filter(produto_pai=produto, ativo=True).select_related("componente")
    return [{"componente": it.componente, "quantidade_por_unidade": it.quantidade_por_unidade} for it in itens]


@transaction.atomic
def consumir_bom(
    produto_final,
    deposito: Deposito,
    quantidade_final: Decimal,
    usuario,
    origem_tipo=None,
    origem_id=None,
    aplicar=True,
):
    if quantidade_final <= 0:
        raise NegocioError("Quantidade final deve ser positiva.")
    componentes = obter_componentes(produto_final)
    if not componentes:
        raise NegocioError("Produto final não possui BOM definida.")
    from estoque.services.valuation import consumir_fifo_e_atualizar, is_fifo

    movimentos = []
    for comp in componentes:
        componente = comp["componente"]
        qtd_comp = (comp["quantidade_por_unidade"] * quantidade_final).quantize(Decimal("0.0001"))
        saldo = EstoqueSaldo.objects.select_for_update().get_or_create(produto=componente, deposito=deposito)[0]
        if saldo.quantidade - saldo.reservado < qtd_comp:
            raise SaldoInsuficienteError(componente.id, deposito.id, qtd_comp, saldo.quantidade - saldo.reservado)
        if aplicar:
            if is_fifo(componente):
                try:
                    custo_unit = consumir_fifo_e_atualizar(componente, deposito, qtd_comp)
                except Exception:
                    custo_unit = saldo.custo_medio
            else:
                custo_unit = saldo.custo_medio
            saldo.quantidade -= qtd_comp
            saldo.save(update_fields=["quantidade", "atualizado_em"])
        else:
            custo_unit = saldo.custo_medio
        mov = MovimentoEstoque.objects.create(
            produto=componente,
            deposito_origem=deposito,
            tipo="CONSUMO_BOM",
            quantidade=qtd_comp,
            custo_unitario_snapshot=custo_unit,
            usuario_executante=usuario,
            solicitante_tipo=origem_tipo,
            solicitante_id=origem_id,
            metadata={"produto_final_id": produto_final.id, "qtd_final": str(quantidade_final)},
        )
        with contextlib.suppress(Exception):
            movimento_registrado.send(sender=MovimentoEstoque, movimento=mov, acao="CONSUMO_BOM")
        movimentos.append(mov)
    # Invalida KPIs globais (ou por tenant se produto_final tiver tenant)
    invalidar_kpis(getattr(produto_final, "tenant", None))
    return movimentos

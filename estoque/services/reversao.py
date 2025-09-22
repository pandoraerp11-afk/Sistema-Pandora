from django.db import transaction

from estoque.models import EstoqueSaldo, MovimentoEstoque
from shared.exceptions import MovimentoNaoReversivelError

REVERSIVEL = {"ENTRADA", "SAIDA", "AJUSTE_POS", "AJUSTE_NEG", "TRANSFER", "DESCARTE", "PERDA", "VENCIMENTO"}


@transaction.atomic
def reverter_movimento(mov: MovimentoEstoque, usuario):
    if mov.reverso_de_id is not None:
        raise MovimentoNaoReversivelError("Movimento já é reversão de outro.")
    if mov.tipo not in REVERSIVEL:
        raise MovimentoNaoReversivelError("Tipo de movimento não reversível.")
    # lógica simples: criar movimento oposto (não anula valuation histórico avançado nesta fase)
    oposto_tipo = None
    if mov.tipo == "ENTRADA":
        oposto_tipo = "AJUSTE_NEG"
    elif mov.tipo == "SAIDA":
        oposto_tipo = "AJUSTE_POS"
    elif mov.tipo == "AJUSTE_POS":
        oposto_tipo = "AJUSTE_NEG"
    elif mov.tipo == "AJUSTE_NEG":
        oposto_tipo = "AJUSTE_POS"
    elif mov.tipo == "TRANSFER":
        oposto_tipo = "TRANSFER"  # invertendo origem/destino
    elif mov.tipo in ["DESCARTE", "PERDA", "VENCIMENTO"]:
        oposto_tipo = "AJUSTE_POS"
    else:
        raise MovimentoNaoReversivelError("Sem tipo oposto configurado.")

    # Atualizar saldos
    if mov.tipo == "ENTRADA":
        saldo = EstoqueSaldo.objects.select_for_update().get(produto=mov.produto, deposito=mov.deposito_destino)
        saldo.quantidade -= mov.quantidade
    elif mov.tipo == "SAIDA":
        saldo = EstoqueSaldo.objects.select_for_update().get(produto=mov.produto, deposito=mov.deposito_origem)
        saldo.quantidade += mov.quantidade
    elif mov.tipo == "TRANSFER":
        saldo_origem = EstoqueSaldo.objects.select_for_update().get(produto=mov.produto, deposito=mov.deposito_origem)
        saldo_destino = EstoqueSaldo.objects.select_for_update().get(produto=mov.produto, deposito=mov.deposito_destino)
        # inverter
        saldo_origem.quantidade += mov.quantidade
        saldo_destino.quantidade -= mov.quantidade
        saldo_origem.save(update_fields=["quantidade", "atualizado_em"])
        saldo_destino.save(update_fields=["quantidade", "atualizado_em"])
    else:  # ajustes e perdas
        deposito = mov.deposito_origem or mov.deposito_destino
        saldo = EstoqueSaldo.objects.select_for_update().get(produto=mov.produto, deposito=deposito)
        if oposto_tipo == "AJUSTE_POS":
            saldo.quantidade += mov.quantidade
        elif oposto_tipo == "AJUSTE_NEG":
            saldo.quantidade -= mov.quantidade
    if mov.tipo != "TRANSFER":
        saldo.save(update_fields=["quantidade", "atualizado_em"])

    reverso = MovimentoEstoque.objects.create(
        produto=mov.produto,
        deposito_origem=mov.deposito_destino if mov.tipo == "TRANSFER" else mov.deposito_origem,
        deposito_destino=mov.deposito_origem if mov.tipo == "TRANSFER" else mov.deposito_destino,
        tipo=oposto_tipo,
        quantidade=mov.quantidade,
        custo_unitario_snapshot=mov.custo_unitario_snapshot,
        usuario_executante=usuario,
        motivo=f"Reversão movimento {mov.id}",
        reverso_de=mov,
        aprovacao_status="APROVADO",
        metadata={"reversao": True, "original": mov.id},
    )
    return reverso

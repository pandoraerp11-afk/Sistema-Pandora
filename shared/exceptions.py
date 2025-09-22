class NegocioError(Exception):
    """Erro de regra de negócio genérico."""

    pass


class SaldoInsuficienteError(NegocioError):
    def __init__(self, produto_id, deposito_id, quantidade_solicitada, quantidade_disponivel):
        self.produto_id = produto_id
        self.deposito_id = deposito_id
        self.quantidade_solicitada = quantidade_solicitada
        self.quantidade_disponivel = quantidade_disponivel
        super().__init__(
            f"Saldo insuficiente para produto={produto_id} deposito={deposito_id}: solicitada={quantidade_solicitada} disponivel={quantidade_disponivel}"
        )


class ReservaInvalidaError(NegocioError):
    pass


class MovimentoNaoReversivelError(NegocioError):
    pass

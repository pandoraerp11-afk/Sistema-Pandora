from estoque.models import MovimentoEstoque, MovimentoEvidencia
from shared.exceptions import NegocioError


def anexar_evidencia(movimento: MovimentoEstoque, arquivo, descricao: str | None = None):
    if movimento.tipo not in ["PERDA", "DESCARTE", "VENCIMENTO"]:
        raise NegocioError("Evidências somente para movimentos de perda/descarte/vencimento.")
    return MovimentoEvidencia.objects.create(movimento=movimento, arquivo=arquivo, descricao=descricao)

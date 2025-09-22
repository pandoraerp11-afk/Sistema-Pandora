from .models import Produto

PREFIXO_PADRAO = "PRD-"
LARGURA_NUMERO = 6


def generate_next_codigo(prefix: str = PREFIXO_PADRAO, width: int = LARGURA_NUMERO) -> str:
    """Gera o próximo código sequencial no formato PREFIXO + número zerado.
    Ex.: PRD-000001, PRD-000002, ...
    Considera apenas códigos que começam com o prefixo informado.
    """
    # Filtrar apenas códigos com o prefixo
    qs = Produto.objects.filter(codigo__startswith=prefix).values_list("codigo", flat=True)
    max_num = 0
    for cod in qs:
        try:
            num_part = cod.replace(prefix, "").strip()
            num = int(num_part)
            max_num = max(max_num, num)
        except Exception:
            # Ignora códigos fora do padrão
            continue
    next_num = max_num + 1
    return f"{prefix}{str(next_num).zfill(width)}"

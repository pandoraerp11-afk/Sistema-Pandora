CARGO_CATALOGO = [
    "Administrador",
    "Diretor",
    "Gerente",
    "Coordenador",
    "Supervisor",
    "Analista",
    "Assistente",
    "Técnico",
    "Financeiro",
    "Comercial",
    "Vendas",
    "Operações",
    "Suporte",
    "RH",
    "TI",
    "Marketing",
]


def normalizar_cargo(valor: str) -> str | None:
    if not valor:
        return None
    v = valor.strip()
    if not v:
        return None
    # Match case-insensitive com catálogo; se não estiver, retorna original truncado
    for c in CARGO_CATALOGO:
        if c.lower() == v.lower():
            return c
    return v[:100]

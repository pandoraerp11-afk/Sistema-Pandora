import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Arquivos que não devem existir mais (consolidados)
OBSOLETOS = {
    "USER_MANAGEMENT_OVERVIEW.md",
    "USER_MANAGEMENT_OPERACOES_FREQUENTES.md",
    "USER_MANAGEMENT_PENDING.md",
    # Permission Resolver consolidado
    "PERMISSION_RESOLVER_ACTIONS.md",
    "PERMISSION_RESOLVER_DECISION_API.md",
    "PERMISSION_RESOLVER_NOTES.md",
    # Prontuários legacy movido
    "PRONTUARIOS_MODERNIZACAO_PLAN.md",
}


def test_docs_obsoletos_nao_existem():
    existentes = set(os.listdir(DOCS)) if DOCS.exists() else set()
    proibidos = OBSOLETOS & existentes
    assert not proibidos, f"Docs obsoletos presentes: {sorted(proibidos)}"


def test_docs_indice_existe():
    idx = DOCS / "INDEX.md"
    assert idx.exists(), "Crie docs/INDEX.md como sumário canônico de documentação"

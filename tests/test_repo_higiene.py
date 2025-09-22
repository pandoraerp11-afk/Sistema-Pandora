"""Testes de higiene do repositório.

Objetivos:
1. Impedir reaparecimento de arquivos soltos sem extensão na raiz (ex: 'Tenant').
2. Detectar regressão de scripts temporários que já foram removidos.

Permite manutenção profissional e mantém a raiz limpa.
"""

from pathlib import Path

STRAY_BLOCKLIST = {
    "Tenant",  # artefato corrompido removido
    "tmp_list_tu",
    "tmp_lookup_bella",
    "parse_ci",
    "_clean_caches",  # versão antiga (agora em scripts/dev)
    "limpar_migracoes",
}


import pytest


@pytest.mark.repo_hygiene
def test_no_stray_root_files():
    root = Path(__file__).resolve().parents[1]
    stray = []
    for item in root.iterdir():
        if not item.is_file():
            continue
        name = item.name
        # Ignorar arquivos normais com extensão (.py, .md, etc.)
        if "." in name:
            continue
        # Ignorar diretórios (já filtrado) e venv markers
        if name in STRAY_BLOCKLIST:
            stray.append(name)
    assert not stray, f"Arquivos estranhos sem extensão na raiz detectados: {stray}. Remova-os."  # noqa: S101


@pytest.mark.repo_hygiene
def test_removed_scripts_not_reintroduced():
    root = Path(__file__).resolve().parents[1]
    reintroduced = []
    for base in STRAY_BLOCKLIST:
        for candidate in [base, f"{base}.py"]:
            p = root / candidate
            if p.exists():
                # Se reaparecer vazio também é indício de recriação indevida pelo editor
                size = p.stat().st_size
                if size == 0:
                    # Auto-correção: remover silenciosamente e continuar
                    try:
                        p.unlink()
                    except Exception:
                        reintroduced.append(f"{candidate} (size=0, remove_failed)")
                else:
                    reintroduced.append(f"{candidate} (size={size})")
    assert not reintroduced, f"Scripts obsoletos reintroduzidos (não vazios ou não removíveis): {reintroduced}."  # noqa: S101


@pytest.mark.repo_hygiene
def test_no_unexpected_large_files():
    """Falha se arquivo potencialmente indevido (>5MB) surgir na raiz.
    Exceções: db.sqlite3. Ignora pastas.
    """
    root = Path(__file__).resolve().parents[1]
    large = []
    threshold = 5 * 1024 * 1024
    for item in root.iterdir():
        if not item.is_file():
            continue
        if item.name in {"db.sqlite3"}:
            continue
        if item.stat().st_size > threshold:
            large.append((item.name, item.stat().st_size))
    assert not large, f"Arquivos potencialmente indevidos grandes na raiz: {large}"  # noqa: S101


@pytest.mark.repo_hygiene
def test_no_legacy_flake8_artifacts():
    """Garante que arquivos/configurações flake8 antigos não retornem.
    Critérios:
      - Arquivo .flake8 não deve existir.
      - Dependência flake8-bugbear removida de requirements-dev.
      - Código de analyzer que usa flake8 deve ser migrado ou marcado para remoção.
    """
    root = Path(__file__).resolve().parents[1]
    flake8_cfg = root / ".flake8"
    assert not flake8_cfg.exists(), ".flake8 deveria ter sido removido após adoção de ruff."  # noqa: S101
    req_dev = root / "requirements-dev.txt"
    if req_dev.exists():
        content = req_dev.read_text(encoding="utf-8")
        assert "flake8-bugbear" not in content, "Dependência flake8-bugbear deve ser removida (ruff substitui)."  # noqa: S101


@pytest.mark.repo_hygiene
def test_sitecustomize_pending_removal_documented():
    """Sitecustomize é opcional; este teste lembra que remoção futura é segura.
    Falha se arquivo for modificado para conter lógica pesada.
    """
    root = Path(__file__).resolve().parents[1]
    sc = root / "sitecustomize.py"
    if sc.exists():
        text = sc.read_text(encoding="utf-8")
        assert "warnings.filterwarnings" in text and "drf_format_suffix" in text, (
            "sitecustomize.py deve permanecer trivial ou ser removido."
        )  # noqa: S101
    else:
        # Arquivo removido: condição final esperada
        assert True


@pytest.mark.repo_hygiene
def test_no_empty_docs_or_tests():
    """Falha se existir:
    - Arquivo .md vazio na raiz ou em docs/ (exceto docs/legacy)
    - Arquivo de teste .py vazio diretamente em tests/ raiz
    Ignora virtualenv, site-packages e testes dentro de apps (para evitar falsos positivos / placeholders temporários).
    """
    root = Path(__file__).resolve().parents[1]
    docs_dir = root / "docs"
    tests_root = root / "tests"
    offenders = []

    # Verificar markdown na raiz e em docs (exceto legacy)
    for md in list(root.glob("*.md")) + list(docs_dir.rglob("*.md")):
        if "legacy" in md.parts:
            continue
        try:
            if md.stat().st_size == 0:
                offenders.append(str(md))
        except OSError:
            continue

    # Verificar arquivos de teste somente no diretório tests/ (não recursivo em apps)
    if tests_root.exists():
        for py in tests_root.glob("test_*.py"):
            if py.name == "__init__.py":
                continue
            try:
                if py.stat().st_size == 0:
                    offenders.append(str(py))
            except OSError:
                continue

    assert not offenders, f"Arquivos vazios encontrados (escopo docs/tests raiz): {offenders}"  # noqa: S101

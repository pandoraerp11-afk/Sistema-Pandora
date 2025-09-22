from pathlib import Path

FORBIDDEN = ["class TenantCreateView", "class TenantUpdateView"]


def test_no_legacy_tenant_class_views_present():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for py in root.rglob("*.py"):
        if py.name == "wizard_views.py":
            continue
        # Ignorar arquivos de testes para evitar falsos positivos (classes mock dentro de testes)
        if "tests" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN:
            if token in text:
                offenders.append(f"{py}:{token}")
    assert not offenders, f"Views legacy detectadas: {offenders}"

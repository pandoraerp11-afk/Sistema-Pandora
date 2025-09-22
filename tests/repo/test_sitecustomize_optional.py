import importlib
import sys
from pathlib import Path

import pytest


@pytest.mark.repo_hygiene
def test_sitecustomize_optional():
    """Valida que ausência real de sitecustomize (removido) não quebra Django.
    Se presente, garante que continua trivial. Se ausente: tudo ok.
    """
    root = Path(__file__).resolve().parents[1]
    sc = root / "sitecustomize.py"
    # Limpa eventual cache
    sys.modules.pop("sitecustomize", None)
    importlib.invalidate_caches()
    from django.conf import settings  # noqa: F401

    if sc.exists():
        text = sc.read_text(encoding="utf-8")
        assert "warnings.filterwarnings" in text, "sitecustomize presente mas não trivial."  # noqa: S101
    else:
        assert True  # explicitamente aceitável

"""Higiene: garante ausência de recriação do diretório legacy core/tests.

Evita reintrodução de estrutura antiga; referências textuais internas também são vetadas.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.hygiene
def test_no_legacy_core_tests_dir() -> None:
    root = Path(__file__).parent
    project_root = root  # tests/ root
    legacy_dir = project_root.parent / "core" / "tests"
    assert (
        not legacy_dir.exists()
    ), "Diretório legacy core/tests reapareceu. Mova os arquivos para tests/core/* e remova a pasta."

    # Também varrer referências textuais suspeitas (exclui backups ou docs)
    offenders: list[Path] = []
    for p in project_root.rglob("*.py"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover
            continue
        if p.name != "test_hygiene_no_core_tests_dir.py" and ("from core.tests" in text or "core/tests/" in text):
            offenders.append(p)
    assert not offenders, "Referências a 'core.tests' encontradas em: " + ", ".join(str(o) for o in offenders)

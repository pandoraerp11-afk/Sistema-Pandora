"""Testes de formatação utilitária JSON.

Inclui wrapper de compatibilidade via ``legacy_imports`` (import * controlado).
"""

import pytest

from core.utils import format_json_text
from tests.core.legacy_imports import *  # noqa: F403


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a":1,"b":2}', '{\n  "a": 1,\n  "b": 2\n}'),
        ("[1,2,3]", "[\n  1,\n  2,\n  3\n]"),
        ("not-json", "not-json"),
        ("", ""),
    ],
)
def test_format_json_text(raw: str, expected: str) -> None:
    """Garante que o utilitário formata ou devolve texto intacto para não-JSON."""
    assert format_json_text(raw) == expected

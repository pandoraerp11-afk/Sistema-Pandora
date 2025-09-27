"""Testes de formatação utilitária JSON."""

import pytest

from core.utils import format_json_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a":1,"b":2}', '{\n  "a": 1,\n  "b": 2\n}'),
        ("[1,2,3]", "[\n  1,\n  2,\n  3\n]"),
        ("not-json", "not-json"),
        ("", ""),
    ],
)
def test_format_json_text(raw, expected):  # noqa: ANN001
    assert format_json_text(raw) == expected


"""Variante de teste de formatação JSON."""
from tests.core.legacy_imports import *  # type: ignore  # noqa: F403

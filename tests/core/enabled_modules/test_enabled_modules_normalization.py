"""Normalização de módulos habilitados."""

import pytest

from core.services.wizard_normalizers import normalize_enabled_modules


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ([], []),
        (["a", "b", "a"], ["a", "b"]),
        ("a,b,a", ["a", "b"]),
        ('["a", "b", "b"]', ["a", "b"]),
        ({"modules": ["m1", "m2", "m1"]}, ["m1", "m2"]),
        ({"legacy": ["x", "y"]}, ["x", "y"]),
        (("z", "w", "z"), ["w", "z"]),
    ],
)
def test_normalize(raw, expected):  # noqa: ANN001
    assert normalize_enabled_modules(raw) == expected


def test_csv_with_spaces():
    assert normalize_enabled_modules(" a , b ,  c ") == ["a", "b", "c"]


"""Bloco adicional de normalização de módulos."""
from tests.core.legacy_imports import *  # noqa: F403

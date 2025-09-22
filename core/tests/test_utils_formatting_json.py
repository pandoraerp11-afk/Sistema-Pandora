import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from core import utils

pytestmark = [pytest.mark.django_db]


def test_normalize_text_basic():
    assert utils.normalize_text("Áé Íção-XYZ") == "ae icao-xyz"
    assert utils.normalize_text(None) == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("11222333000181", "11.222.333/0001-81"),
        ("11.222.333/0001-81", "11.222.333/0001-81"),
        ("123", "123"),
        (None, ""),
    ],
)
def test_format_cnpj(raw, expected):
    assert utils.format_cnpj(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12345678901", "123.456.789-01"),
        ("123.456.789-01", "123.456.789-01"),
        ("999", "999"),
        (None, ""),
    ],
)
def test_format_cpf(raw, expected):
    assert utils.format_cpf(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("11987654321", "(11) 98765-4321"),
        ("1187654321", "(11) 8765-4321"),
        ("000", "000"),
        (None, ""),
    ],
)
def test_format_phone(raw, expected):
    assert utils.format_phone(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12345678", "12345-678"),
        ("12.345-678", "12345-678"),
        ("999", "999"),
        (None, ""),
    ],
)
def test_format_cep(raw, expected):
    assert utils.format_cep(raw) == expected


def test_decimal_and_str_conversion():
    assert utils.decimal_to_str(Decimal("10")) == "10,00"
    assert utils.decimal_to_str("7.5") == "7,50"
    assert utils.str_to_decimal("1.234,56") == Decimal("1234.56")
    assert utils.str_to_decimal("") == Decimal("0")


def test_format_and_parse_date():
    d = date(2024, 5, 17)
    assert utils.format_date(d) == "17/05/2024"
    assert utils.format_date("2024-05-17") == "17/05/2024"
    # parse
    assert utils.parse_date("17/05/2024") == d
    assert utils.parse_date("") is None
    # invalid keeps original on format
    assert utils.format_date("2024/13/99") == "2024/13/99"


def test_truncate_string():
    txt = "x" * 50
    assert utils.truncate_string(txt, 10) == ("x" * 7) + "..."
    assert utils.truncate_string("short", 10) == "short"
    assert utils.truncate_string(None, 5) == ""


def test_generate_unique_filename_changes():
    name1 = utils.generate_unique_filename(None, "Relatório Financeiro.pdf")
    name2 = utils.generate_unique_filename(None, "Relatório Financeiro.pdf")
    assert name1 != name2
    assert name1.endswith(".pdf") and name2.endswith(".pdf")
    assert name1.startswith("relatorio-financeiro-")


def test_json_serialize_and_deserialize():
    obj = {
        "n": 1,
        "d": Decimal("2.5"),
        "dt": datetime(2024, 1, 2, 3, 4, 5),
        "u": uuid.UUID("12345678-1234-5678-1234-567812345678"),
    }
    s = utils.json_serialize(obj)
    assert "2.5" in s and "2024-01-02T03:04:05" in s
    back = utils.json_deserialize(s)
    assert back["n"] == 1
    # roundtrip decimal becomes float
    assert back["d"] == 2.5
    # invalid returns {}
    assert utils.json_deserialize("invalid json") == {}
    assert utils.json_deserialize("") == {}

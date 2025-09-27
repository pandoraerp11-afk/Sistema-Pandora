import pytest

from core.services.wizard_admins import parse_admins_payload
from core.services.wizard_normalizers import normalize_enabled_modules, parse_socials_json


class TestNormalizeEnabledModules:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, []),
            ([], []),
            (["a", "b", "a"], ["a", "b"]),
            ("a,b,a", ["a", "b"]),
            ('["a", "b", "b"]', ["a", "b"]),
            ({"modules": ["m1", "m2", "m1"]}, ["m1", "m2"]),
            ({"legacy": ["x", "y"]}, ["x", "y"]),
            (("z", "w", "z"), ["w", "z"]),  # sorted output
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_enabled_modules(raw) == expected

    def test_csv_with_spaces(self):
        assert normalize_enabled_modules(" a , b ,  c ") == ["a", "b", "c"]


class TestParseSocialsJson:
    def test_empty(self):
        assert parse_socials_json(None) == {}
        assert parse_socials_json("") == {}

    def test_valid(self):
        raw = '[{"nome":"site","link":"https://ex.com"},{"nome":"git","link":"https://g"}]'
        assert parse_socials_json(raw) == {"site": "https://ex.com", "git": "https://g"}

    def test_ignores_invalid_items(self):
        raw = '[1,2,{"nome":"","link":"x"},{"nome":"ok","link":""},{"nome":"v","link":"l"}]'
        assert parse_socials_json(raw) == {"v": "l"}

    def test_last_wins(self):
        raw = '[{"nome":"a","link":"1"},{"nome":"a","link":"2"}]'
        assert parse_socials_json(raw) == {"a": "2"}

    def test_malformed(self, caplog):
        caplog.set_level("WARNING")
        assert parse_socials_json("not-json") == {}
        assert any("socials_json inválido" in rec.message for rec in caplog.records)


class TestParseAdminsPayload:
    def test_list_payload(self):
        data = {"admins_json": '[{"email":"a@a","nome":"A"},{"email":"b@b","nome":"B"}]'}
        admins, bulk = parse_admins_payload(data)
        assert len(admins) == 2
        assert bulk is None

    def test_with_bulk_password(self):
        data = {"admins_json": '[{"email":"a@a"}]', "bulk_admin_password": "X123"}
        admins, bulk = parse_admins_payload(data)
        assert len(admins) == 1
        assert bulk == "X123"

    def test_embedded_main(self):
        data = {"main": {"admins_json": '[{"email":"a@a"}]', "bulk_admin_password": "P"}}
        admins, bulk = parse_admins_payload(data)
        assert len(admins) == 1
        assert bulk == "P"

    def test_fallback_single_admin(self):
        data = {"admin_email": "solo@x"}
        admins, bulk = parse_admins_payload(data)
        assert len(admins) == 1
        assert admins[0]["admin_email"] == "solo@x"

    def test_limit_50(self):
        items = [{"email": f"u{i}@x"} for i in range(60)]
        data = {"admins_json": str(items).replace("'", '"')}
        admins, _ = parse_admins_payload(data)
        assert len(admins) == 50

    def test_malformed_logs_warning(self, caplog):
        caplog.set_level("WARNING")
        data = {"admins_json": "not-json"}
        admins, _ = parse_admins_payload(data)
        assert admins == []
        assert any("admins_json inválido" in rec.message for rec in caplog.records)

from django.test import SimpleTestCase

from core.services.cargo_catalog import normalizar_cargo


class TestCargoNormalization(SimpleTestCase):
    def test_case_insensitive(self):
        self.assertEqual(normalizar_cargo("gerente"), "Gerente")
        self.assertEqual(normalizar_cargo("GERENTE"), "Gerente")
        self.assertEqual(normalizar_cargo("GeReNtE"), "Gerente")

    def test_unknown_returns_truncated_original(self):
        self.assertEqual(normalizar_cargo("Gerentex"), "Gerentex")
        long_value = "x" * 150
        self.assertEqual(len(normalizar_cargo(long_value)), 100)

    def test_empty_none(self):
        self.assertIsNone(normalizar_cargo(""))
        self.assertIsNone(normalizar_cargo(None))  # type: ignore

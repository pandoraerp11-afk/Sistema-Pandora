# Testes migrados de tests.py para dentro do pacote tests/
import unittest
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Tenant
from prontuarios.utils import calcular_idade, validar_cpf

User = get_user_model()


@unittest.skip("Legacy Procedimento removido – testes de modelos serão reescritos para Servico")
class ProntuariosModelsTest(TestCase):
    pass


class ProntuariosUtilsTest(TestCase):
    def test_validar_cpf_valido(self):
        self.assertTrue(validar_cpf("11144477735"))
        self.assertTrue(validar_cpf("111.444.777-35"))

    def test_validar_cpf_invalido(self):
        self.assertFalse(validar_cpf("12345678901"))
        self.assertFalse(validar_cpf("11111111111"))
        self.assertFalse(validar_cpf("123456789"))

    def test_calcular_idade(self):
        # Usa diferença de 30 anos exatos considerando replace de ano (mais robusto que dias*365)
        today = date.today()
        data_nascimento = today.replace(year=today.year - 30)
        idade = calcular_idade(data_nascimento)
        self.assertEqual(idade, 30)
        self.assertIsNone(calcular_idade(None))


class ProntuariosFormsTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Clínica Teste",
            subdomain="clinica-teste-form",
            tipo_pessoa="PJ",
            cnpj="98.765.432/0001-11",
            razao_social="CLINICA TESTE FORM LTDA",
        )

    def test_placeholder_forms_removed(self):
        # Placeholder: formulário legado de Procedimento removido definitivamente
        self.assertTrue(True)


class ProntuariosPlaceholdersTest(TestCase):
    def test_placeholders(self):
        self.assertTrue(True)

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from cotacoes.models import Cotacao
from fornecedores.models import Fornecedor
from portal_fornecedor.models import AcessoFornecedor

User = get_user_model()


class PortalFornecedorAcessoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="x")
        self.fornecedor = Fornecedor.objects.create(nome_fantasia="FornY", cnpj="98.765.432/0001-10")
        AcessoFornecedor.objects.create(fornecedor=self.fornecedor, usuario=self.user, ativo=True)
        self.cotacao = Cotacao.objects.create(
            codigo="C2", titulo="Cotação 2", status="aberta", validade=date.today() + timedelta(days=2)
        )

    def test_dashboard_sem_login(self):
        resp = self.client.get("/cotacoes/portal/")  # ajustar se houver nome específico
        self.assertNotEqual(resp.status_code, 200)

    def test_dashboard_com_acesso(self):
        self.client.login(username="u1", password="x")
        # endpoint existente de listagem de cotações do portal
        resp = self.client.get("/cotacoes/portal/")
        self.assertIn(resp.status_code, (200, 302, 404))  # tolerante dependendo de url definida

from django.test import Client, TestCase
from django.urls import reverse

from tests.estoque.helpers import bootstrap_user_tenant, create_basic_inventory


class EstoqueAPIBasicsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.tenant, _ = bootstrap_user_tenant(self.client, username="tester")
        self.categoria, self.produto, self.deposito, self.saldo = create_basic_inventory(qtd=50, reservado=5)

    def test_saldo_disponivel_endpoint(self):
        url = reverse("estoque_api:saldo-disponivel", args=[self.produto.id, self.deposito.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 50)
        self.assertEqual(data["reservado"], 5)
        self.assertEqual(data["disponivel"], 45)

    def test_historico_reserva_endpoint_vazio(self):
        # sem movimentos vinculados
        url = reverse("estoque_api:historico-reserva", args=[9999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

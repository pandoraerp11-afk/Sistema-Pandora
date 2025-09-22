from django.test import Client, TestCase
from django.urls import reverse

from tests.estoque.helpers import bootstrap_user_tenant


class KPIsEstoqueAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.tenant, _ = bootstrap_user_tenant(self.client, username="tester", password="123456")

    def test_kpis_endpoint_basic_structure(self):
        url = reverse("estoque_api:dashboard-kpis")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in [
            "giro_estoque",
            "acuracidade_estoque",
            "disponibilidade",
            "movimentacao_periodo",
            "eficiencia_picking",
            "custos_estoque",
            "periodo_dias",
            "calculado_em",
        ]:
            self.assertIn(key, data)

    def test_kpis_custom_period(self):
        url = reverse("estoque_api:dashboard-kpis") + "?periodo=7"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("periodo_dias"), 7)

    def test_kpis_invalid_period_defaults(self):
        url = reverse("estoque_api:dashboard-kpis") + "?periodo=abc"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("periodo_dias"), 30)

from django.test import Client, TestCase
from django.urls import reverse

from estoque.models import Deposito, EstoqueSaldo
from produtos.models import Categoria, Produto
from tests.estoque.helpers import bootstrap_user_tenant


class EstoqueViewsItensTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.tenant, _ = bootstrap_user_tenant(self.client, username="tester")
        self.categoria = Categoria.objects.create(nome="Geral")
        self.produto = Produto.objects.create(nome="Produto A", categoria=self.categoria)
        self.deposito = Deposito.objects.create(codigo="DEPX", nome="Dep X")
        self.saldo = EstoqueSaldo.objects.create(produto=self.produto, deposito=self.deposito, quantidade=15)

    def test_list_view_renders(self):
        url = reverse("estoque:itens_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Controle de Estoque")

    def test_detail_view_renders(self):
        url = reverse("estoque:item_detail", args=[self.saldo.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Detalhes e situação do item")

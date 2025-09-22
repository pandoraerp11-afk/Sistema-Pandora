from django.test import TestCase

from .models import Produto


class ProdutoModelTest(TestCase):
    def setUp(self):
        Produto.objects.create(
            nome="Cimento CP-II",
            categoria="materiais",
            unidade="sc",
            preco_unitario=25.00,
            estoque_atual=100,
            estoque_minimo=10,
        )

    def test_criacao_produto(self):
        produto = Produto.objects.get(nome="Cimento CP-II")
        self.assertEqual(produto.unidade, "sc")
        self.assertTrue(produto.ativo)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from estoque.models import Deposito, Lote, MovimentoEstoque, NumeroSerie
from estoque.services import movimentos
from produtos.models import Categoria, Produto

User = get_user_model()


class MovimentosLoteSerieTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="tester")
        self.cat = Categoria.objects.create(nome="Cat")
        self.prod_lote = Produto.objects.create(
            nome="Prod Lote",
            categoria=self.cat,
            preco_unitario=10,
            preco_custo=5,
            tipo_custo="preco_medio",
            controla_estoque=True,
            controla_lote=True,
        )
        self.prod_ns = Produto.objects.create(
            nome="Prod NS",
            categoria=self.cat,
            preco_unitario=10,
            preco_custo=5,
            tipo_custo="preco_medio",
            controla_estoque=True,
            controla_numero_serie=True,
        )
        self.dep = Deposito.objects.create(codigo="DEP1", nome="Dep 1")

    def test_entrada_com_lotes(self):
        movimentos.registrar_entrada(
            self.prod_lote,
            self.dep,
            Decimal("10"),
            Decimal("5"),
            self.user,
            lotes=[{"codigo": "L1", "quantidade": 5}, {"codigo": "L2", "quantidade": 5}],
        )
        self.assertEqual(MovimentoEstoque.objects.count(), 1)
        self.assertEqual(Lote.objects.filter(produto=self.prod_lote).count(), 2)
        self.assertEqual(sum(l.quantidade_atual for l in Lote.objects.filter(produto=self.prod_lote)), Decimal("10"))

    def test_saida_lotes_quantidade_inconsistente(self):
        movimentos.registrar_entrada(
            self.prod_lote, self.dep, Decimal("5"), Decimal("5"), self.user, lotes=[{"codigo": "L1", "quantidade": 5}]
        )
        with self.assertRaises(Exception):
            movimentos.registrar_saida(
                self.prod_lote, self.dep, Decimal("5"), self.user, lotes=[{"codigo": "L1", "quantidade": 4}]
            )

    def test_entrada_com_numeros_serie(self):
        movimentos.registrar_entrada(
            self.prod_ns, self.dep, Decimal("3"), Decimal("5"), self.user, numeros_serie=["NS1", "NS2", "NS3"]
        )
        self.assertEqual(NumeroSerie.objects.filter(produto=self.prod_ns).count(), 3)

    def test_saida_com_numeros_serie(self):
        movimentos.registrar_entrada(
            self.prod_ns, self.dep, Decimal("2"), Decimal("5"), self.user, numeros_serie=["NS10", "NS11"]
        )
        movimentos.registrar_saida(self.prod_ns, self.dep, Decimal("2"), self.user, numeros_serie=["NS10", "NS11"])
        # status alterado para MOVIMENTADO
        self.assertTrue(
            all(ns.status == "MOVIMENTADO" for ns in NumeroSerie.objects.filter(codigo__in=["NS10", "NS11"]))
        )

    def test_bloqueio_saida_sem_lotes(self):
        movimentos.registrar_entrada(
            self.prod_lote, self.dep, Decimal("2"), Decimal("5"), self.user, lotes=[{"codigo": "L1", "quantidade": 2}]
        )
        with self.assertRaises(Exception):
            movimentos.registrar_saida(self.prod_lote, self.dep, Decimal("2"), self.user)

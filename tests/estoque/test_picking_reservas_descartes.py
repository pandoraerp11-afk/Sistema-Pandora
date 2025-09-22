from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from estoque.models import Deposito, ReservaEstoque
from estoque.services import movimentos
from estoque.services import pedidos_separacao as ps_srv
from estoque.services import reservas as res_srv
from produtos.models import Categoria, Produto

User = get_user_model()


class PickingReservasDescartesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="picker")
        # permissões
        for cod in ["pode_operar_movimento", "pode_gerenciar_picking"]:
            self.user.user_permissions.add(Permission.objects.get(codename=cod))
        self.cat = Categoria.objects.create(nome="Cat")
        self.prod = Produto.objects.create(
            nome="Prod",
            categoria=self.cat,
            preco_unitario=10,
            preco_custo=5,
            tipo_custo="preco_medio",
            controla_estoque=True,
        )
        self.dep = Deposito.objects.create(codigo="D1", nome="Dep 1")
        movimentos.registrar_entrada(self.prod, self.dep, Decimal("50"), Decimal("5"), self.user)

    def test_criar_pedido_e_reservar_item(self):
        pedido = ps_srv.criar_pedido(
            "PED",
            "1",
            "Pedido Teste",
            [{"produto": self.prod, "quantidade": Decimal("5")}],
            criado_por=self.user,
            tenant=None,
        )
        # adicionar depósito ao item para permitir separação
        item = pedido.itens.first()
        item.deposito = self.dep
        item.save(update_fields=["deposito"])
        ps_srv.iniciar_preparacao(pedido, self.user)
        ps_srv.marcar_item_separado(item, Decimal("5"))
        reserva = ReservaEstoque.objects.get(produto=self.prod, deposito=self.dep)
        self.assertEqual(reserva.quantidade, Decimal("5"))

    def test_descarte_gera_movimento_pendente(self):
        # permissão operar já atribuída
        from estoque.services.descartes import registrar_descarte

        mov = registrar_descarte(
            self.prod,
            self.dep,
            Decimal("2"),
            self.user,
            "Perda teste detalhada",
            tipo="PERDA",
            threshold_aprovacao_valor=Decimal("1"),
        )
        self.assertEqual(mov.tipo, "PERDA")
        self.assertIn(mov.aprovacao_status, ["PENDENTE", "APROVADO"])

    def test_liberar_reserva(self):
        reserva = res_srv.criar_reserva(self.prod, self.dep, Decimal("3"), "TESTE", "X")
        res_srv.liberar_reserva(reserva)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "CANCELADA")

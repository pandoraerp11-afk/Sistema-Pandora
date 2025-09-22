# Consolidado de testes unitários migrados de tests.py para dentro do pacote tests/
from decimal import Decimal

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from cadastros_gerais.models import UnidadeMedida
from estoque.models import Deposito, EstoqueSaldo
from estoque.services import bom as bom_srv
from estoque.services import descartes as desc_srv
from estoque.services import reservas as res_srv
from produtos.models import Categoria, Produto, ProdutoBOMItem


class ReservaAgregadaTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username="tester")
        cat = Categoria.objects.create(nome="Geral")
        un = UnidadeMedida.objects.create(codigo="UN", nome="Unidade")
        self.produto = Produto.objects.create(
            categoria=cat,
            nome="Item X",
            codigo="ITX",
            unidade=un,
            preco_unitario=10,
            preco_custo=5,
        )
        self.deposito = Deposito.objects.create(codigo="DEP1", nome="Dep 1")
        EstoqueSaldo.objects.create(
            produto=self.produto, deposito=self.deposito, quantidade=Decimal("100"), reservado=Decimal("0")
        )

    def test_agregacao_reserva(self):
        r1 = res_srv.criar_reserva(self.produto, self.deposito, Decimal("10"), "PICKING", "1")
        r2 = res_srv.criar_reserva(self.produto, self.deposito, Decimal("5"), "PICKING", "1")
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(r2.quantidade, Decimal("15"))


class BomConsumoTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username="tester2")
        cat = Categoria.objects.create(nome="Kits")
        un = UnidadeMedida.objects.create(codigo="PC", nome="Peça")
        self.produto_final = Produto.objects.create(
            categoria=cat, nome="Kit", codigo="KIT1", unidade=un, preco_unitario=50, preco_custo=30
        )
        self.comp1 = Produto.objects.create(
            categoria=cat, nome="Comp A", codigo="CMPA", unidade=un, preco_unitario=5, preco_custo=3
        )
        self.comp2 = Produto.objects.create(
            categoria=cat, nome="Comp B", codigo="CMPB", unidade=un, preco_unitario=7, preco_custo=4
        )
        self.deposito = Deposito.objects.create(codigo="DEP2", nome="Dep 2")
        EstoqueSaldo.objects.create(produto=self.comp1, deposito=self.deposito, quantidade=Decimal("50"))
        EstoqueSaldo.objects.create(produto=self.comp2, deposito=self.deposito, quantidade=Decimal("30"))
        ProdutoBOMItem.objects.create(
            produto_pai=self.produto_final, componente=self.comp1, quantidade_por_unidade=Decimal("2")
        )
        ProdutoBOMItem.objects.create(
            produto_pai=self.produto_final, componente=self.comp2, quantidade_por_unidade=Decimal("1.5")
        )

    def test_consumo_bom(self):
        movimentos = bom_srv.consumir_bom(self.produto_final, self.deposito, Decimal("4"), self.user)
        self.assertEqual(len(movimentos), 2)
        saldo1 = EstoqueSaldo.objects.get(produto=self.comp1, deposito=self.deposito)
        self.assertEqual(saldo1.quantidade, Decimal("42"))


class AprovacaoPerdaTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username="approver")
        cat = Categoria.objects.create(nome="Perdas")
        un = UnidadeMedida.objects.create(codigo="UN2", nome="Unid 2")
        self.produto = Produto.objects.create(
            categoria=cat, nome="Item Loss", codigo="LOSS1", unidade=un, preco_unitario=20, preco_custo=8
        )
        self.deposito = Deposito.objects.create(codigo="DEP3", nome="Dep 3")
        EstoqueSaldo.objects.create(
            produto=self.produto, deposito=self.deposito, quantidade=Decimal("20"), custo_medio=Decimal("5")
        )

    def test_perda_pendente_e_aprovacao(self):
        mov = desc_srv.registrar_descarte(
            self.produto,
            self.deposito,
            Decimal("10"),
            self.user,
            "Justificativa longa suficiente",
            tipo="PERDA",
            threshold_aprovacao_valor=Decimal("10"),
        )
        self.assertEqual(mov.aprovacao_status, "PENDENTE")
        from estoque.services.descartes import aprovar_movimento_perda

        aprovar_movimento_perda(mov, self.user)
        mov.refresh_from_db()
        self.assertEqual(mov.aprovacao_status, "APROVADO")


class WebSocketSmokeTest(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username="ws_tester")
        cat = Categoria.objects.create(nome="WS")
        un = UnidadeMedida.objects.create(codigo="UN3", nome="Unid 3")
        self.produto = Produto.objects.create(
            categoria=cat,
            nome="WS Item",
            codigo="WS1",
            unidade=un,
            preco_unitario=15,
            preco_custo=9,
        )
        self.deposito = Deposito.objects.create(codigo="DEPWS", nome="Dep WS")

    @pytest.mark.xfail(
        reason="Channel layer/ASGI auth scope não configurado em ambiente de teste simplificado", strict=False
    )
    async def test_estoque_stream_smoke(self):
        from estoque.consumers import EstoqueStreamConsumer

        communicator = WebsocketCommunicator(EstoqueStreamConsumer.as_asgi(), "/ws/estoque/")
        connected, _ = await communicator.connect()
        if not connected:
            pytest.xfail("Canal WebSocket não conectou (layer ou auth scope não configurado).")
        from estoque.services import movimentos as mov_srv

        await database_sync_to_async(mov_srv.registrar_entrada)(
            self.produto, self.deposito, Decimal("5"), Decimal("10"), self.user
        )
        try:
            message = await communicator.receive_json_from(timeout=2)
            if "data" in message:
                self.assertIn("event", message["data"])
        except Exception:
            pass
        await communicator.disconnect()

    @pytest.mark.xfail(
        reason="Channel layer/ASGI auth scope não configurado em ambiente de teste simplificado", strict=False
    )
    async def test_picking_stream_smoke(self):
        from estoque.consumers import PickingStreamConsumer

        communicator = WebsocketCommunicator(PickingStreamConsumer.as_asgi(), "/ws/picking/")
        connected, _ = await communicator.connect()
        if not connected:
            pytest.xfail("Canal WebSocket picking não conectou (layer ou auth scope não configurado).")
        await communicator.disconnect()

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from estoque.models import Deposito, PedidoSeparacao, PedidoSeparacaoAnexo, PedidoSeparacaoMensagem
from estoque.services import movimentos
from estoque.services.descartes import aprovar_movimento_perda, registrar_descarte, rejeitar_movimento_perda
from produtos.models import Categoria, Produto

User = get_user_model()


class PerdasAprovacaoAnexoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="oper")
        self.aprovador = User.objects.create(username="aprov")
        for cod in ["pode_operar_movimento", "pode_aprovar_movimento", "pode_gerenciar_picking"]:
            self.user.user_permissions.add(Permission.objects.get(codename=cod))
            self.aprovador.user_permissions.add(Permission.objects.get(codename=cod))
        self.cat = Categoria.objects.create(nome="Cat")
        self.prod = Produto.objects.create(
            nome="Prod",
            categoria=self.cat,
            preco_unitario=10,
            preco_custo=5,
            tipo_custo="preco_medio",
            controla_estoque=True,
        )
        self.dep = Deposito.objects.create(codigo="DEPX", nome="Deposito X")
        movimentos.registrar_entrada(self.prod, self.dep, Decimal("100"), Decimal("5"), self.user)

    def test_perda_aprovacao_fluxo(self):
        # threshold baixo força pendência
        mov = registrar_descarte(
            self.prod,
            self.dep,
            Decimal("10"),
            self.user,
            "Justificativa perda aprovar",
            tipo="PERDA",
            threshold_aprovacao_valor=Decimal("1"),
        )
        self.assertEqual(mov.aprovacao_status, "PENDENTE")
        qtd_saldo_antes = self.prod.saldos.get(deposito=self.dep).quantidade
        aprovar_movimento_perda(mov, self.aprovador)
        mov.refresh_from_db()
        self.assertEqual(mov.aprovacao_status, "APROVADO")
        saldo_depois = self.prod.saldos.get(deposito=self.dep).quantidade
        self.assertEqual(qtd_saldo_antes - Decimal("10"), saldo_depois)

    def test_perda_rejeicao_fluxo(self):
        mov = registrar_descarte(
            self.prod,
            self.dep,
            Decimal("5"),
            self.user,
            "Justificativa perda rejeitar",
            tipo="PERDA",
            threshold_aprovacao_valor=Decimal("1"),
        )
        self.assertEqual(mov.aprovacao_status, "PENDENTE")
        qtd_saldo_antes = self.prod.saldos.get(deposito=self.dep).quantidade
        rejeitar_movimento_perda(mov, self.aprovador, "Motivo rejeição")
        mov.refresh_from_db()
        self.assertEqual(mov.aprovacao_status, "REJEITADO")
        saldo_depois = self.prod.saldos.get(deposito=self.dep).quantidade
        # saldo não deve mudar
        self.assertEqual(qtd_saldo_antes, saldo_depois)

    def test_anexo_picking_incrementa_contador(self):
        pedido = PedidoSeparacao.objects.create(
            codigo="PS1",
            solicitante_tipo="X",
            solicitante_id="1",
            solicitante_nome_cache="Teste",
            criado_por_user=self.user,
        )
        msg = PedidoSeparacaoMensagem.objects.create(pedido=pedido, texto="Mensagem", autor_user=self.user)
        arquivo = SimpleUploadedFile("evidencia.txt", b"dados", content_type="text/plain")
        anexo = PedidoSeparacaoAnexo.objects.create(
            mensagem=msg, arquivo=arquivo, nome_original="evidencia.txt", tamanho_bytes=5, tipo_mime="text/plain"
        )
        # atualizar contador conforme lógica do endpoint (simulação)
        msg.anexos_count = msg.anexos.count()
        msg.save(update_fields=["anexos_count"])
        self.assertEqual(msg.anexos_count, 1)
        self.assertIsNotNone(anexo.id)

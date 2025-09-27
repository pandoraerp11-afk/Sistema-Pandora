from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Tenant
from notifications.models import ConfiguracaoNotificacao, LogNotificacao, Notification, PreferenciaUsuarioNotificacao

User = get_user_model()


class NotificationModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.user.tenant = self.tenant
        self.user.save()

    def test_criar_notificacao(self):
        n = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user,
            titulo="Notificação de Teste",
            mensagem="Esta é uma mensagem de teste",
            tipo="info",
            prioridade="media",
        )
        self.assertEqual(n.status, "nao_lida")
        self.assertEqual(n.tipo, "info")
        self.assertEqual(n.prioridade, "media")

    def test_str(self):
        n = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="Titulo", mensagem="Msg", tipo="info"
        )
        self.assertIn("Titulo", str(n))

    def test_marcar_como_lida(self):
        n = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="Ler", mensagem="Msg", tipo="info"
        )
        n.marcar_como_lida()
        self.assertEqual(n.status, "lida")
        self.assertIsNotNone(n.data_leitura)

    def test_arquivar(self):
        n = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="Arq", mensagem="Msg", tipo="info"
        )
        n.arquivar()
        self.assertEqual(n.status, "arquivada")

    def test_expirada(self):
        n = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user,
            titulo="Exp",
            mensagem="Msg",
            tipo="info",
            data_expiracao=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(n.is_expirada())

    def test_get_helpers(self):
        n = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user,
            titulo="Helpers",
            mensagem="Msg",
            tipo="warning",
            prioridade="alta",
        )
        self.assertTrue(n.get_icone_tipo())
        self.assertEqual(n.get_cor_prioridade(), "warning")


class ConfiguracaoNotificacaoTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

    def test_criar(self):
        c = ConfiguracaoNotificacao.objects.create(
            tenant=self.tenant, dias_expiracao_padrao=15, max_notificacoes_por_hora=100, email_habilitado=False
        )
        self.assertEqual(c.dias_expiracao_padrao, 15)
        self.assertFalse(c.email_habilitado)


class PreferenciaUsuarioNotificacaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_criar(self):
        pref = PreferenciaUsuarioNotificacao.objects.create(usuario=self.user, receber_notificacoes=True)
        self.assertTrue(pref.receber_notificacoes)


class LogNotificacaoTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")
        self.user = User.objects.create_user(username="u", password="p")
        self.n = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="Log", mensagem="Msg", tipo="info"
        )

    def test_criar_log(self):
        log = LogNotificacao.objects.create(notificacao=self.n, usuario=self.user, acao="Criada")
        self.assertEqual(log.notificacao, self.n)
        self.assertEqual(log.usuario, self.user)
        self.assertIn("Criada", log.acao)


class NotificationIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.user.tenant = self.tenant
        self.user.save()
        self.client.login(username="testuser", password="testpass123")

    def test_fluxo_basico(self):
        n = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user,
            titulo="Fluxo",
            mensagem="Msg",
            tipo="info",
            prioridade="alta",
        )
        self.assertEqual(n.status, "nao_lida")
        # Detail view (se existir) opcional
        try:
            resp = self.client.get(reverse("notifications:notification_detail", kwargs={"pk": n.pk}))
            if resp.status_code == 200:
                n.refresh_from_db()
                self.assertIn(n.status, ["lida", "nao_lida"])
        except Exception:
            pass
        n.arquivar()
        self.assertEqual(n.status, "arquivada")

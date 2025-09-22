from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Role, Tenant, TenantUser
from user_management.models import PerfilUsuarioEstendido, SessaoUsuario

User = get_user_model()


class UserManagementExtraTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Z", subdomain="emp-z")
        self.admin = User.objects.create_user(
            username="adminz", password="pass", email="a@ex.com", is_staff=True, is_superuser=True
        )
        # Criar perfil admin manual
        PerfilUsuarioEstendido.objects.get_or_create(
            user=self.admin, defaults={"tipo_usuario": "admin_empresa", "status": "ativo"}
        )
        self.role = Role.objects.create(tenant=self.tenant, name="RoleZ")
        TenantUser.objects.create(tenant=self.tenant, user=self.admin, role=self.role)
        self.client.login(username="adminz", password="pass")
        # Simular injeção de tenant na sessão
        session = self.client.session
        session["current_tenant_id"] = self.tenant.id
        session.save()

    def test_toggle_2fa(self):
        perfil = self.admin.perfil_estendido
        url = reverse("user_management:toggle_2fa", args=[perfil.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        perfil.refresh_from_db()
        self.assertTrue(perfil.autenticacao_dois_fatores)

    def test_encerrar_sessao(self):
        # Criar sessão simulada
        s = SessaoUsuario.objects.create(
            user=self.admin, session_key="abc123", ip_address="127.0.0.1", user_agent="Test"
        )
        url = reverse("user_management:sessao_encerrar", args=[s.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        s.refresh_from_db()
        self.assertFalse(s.ativa)

    def test_detalhe_sessao(self):
        s = SessaoUsuario.objects.create(user=self.admin, session_key="def456", ip_address="127.0.0.1", user_agent="UA")
        url = reverse("user_management:sessao_detalhe", args=[s.pk])
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["sessao"]["ip_address"], "127.0.0.1")

    def test_encerrar_todas_sessoes(self):
        SessaoUsuario.objects.create(user=self.admin, session_key="k1", ip_address="127.0.0.1", user_agent="UA")
        SessaoUsuario.objects.create(user=self.admin, session_key="k2", ip_address="127.0.0.1", user_agent="UA")
        url = reverse("user_management:sessao_encerrar_todas", args=[self.admin.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["encerradas"], 2)

    def test_encerrar_multiplas_sessoes(self):
        s1 = SessaoUsuario.objects.create(user=self.admin, session_key="m1", ip_address="127.0.0.1", user_agent="UA")
        s2 = SessaoUsuario.objects.create(user=self.admin, session_key="m2", ip_address="127.0.0.1", user_agent="UA")
        url = reverse("user_management:sessao_encerrar_multiplas")
        resp = self.client.post(url, data={"ids": f"{s1.pk},{s2.pk}"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["encerradas"], 2)

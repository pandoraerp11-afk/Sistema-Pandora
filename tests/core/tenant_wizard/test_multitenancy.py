"""Testes de multitenancy compatíveis com o modelo atual.

Valida:
 - Alias slug/subdomain
 - Método is_active()
 - Property modules e has_module para formatos legado e novo
 - TenantUser com Role relacional e flag is_tenant_admin
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Modulo, Role, Tenant, TenantUser


class TestTenantModel(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste", status="active")

    def test_fields_and_slug_alias(self):
        self.assertEqual(self.tenant.name, "Empresa Teste")
        self.assertEqual(self.tenant.subdomain, "empresa-teste")
        self.assertEqual(self.tenant.slug, "empresa-teste")

    def test_is_active_toggle(self):
        self.assertTrue(self.tenant.is_active())
        self.tenant.status = "inactive"
        self.tenant.save()
        self.assertFalse(self.tenant.is_active())

    def test_modules_property_formats(self):
        self.tenant.modules = {"clientes": {"enabled": True}, "estoque": {"enabled": False}}
        self.assertTrue(self.tenant.has_module("clientes"))
        self.assertFalse(self.tenant.has_module("estoque"))
        self.tenant.modules = {"modules": ["financeiro", "documentos"]}
        self.assertTrue(self.tenant.has_module("financeiro"))
        self.assertFalse(self.tenant.has_module("clientes"))


class TestTenantUserModel(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa A", subdomain="empresa-a", status="active")
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="x")
        self.role_admin = Role.objects.create(tenant=self.tenant, name="admin")
        self.tu = TenantUser.objects.create(
            tenant=self.tenant, user=self.user, role=self.role_admin, is_tenant_admin=True
        )

    def test_creation_and_str(self):
        self.assertEqual(self.tu.tenant, self.tenant)
        self.assertEqual(self.tu.user, self.user)
        self.assertIn(self.user.username, str(self.tu))

    def test_is_admin_flag(self):
        self.assertTrue(self.tu.is_tenant_admin)
        self.tu.is_tenant_admin = False
        self.tu.save()
        self.assertFalse(self.tu.is_tenant_admin)


class TestModuloModel(TestCase):
    def setUp(self):
        self.mod = Modulo.objects.create(nome="Clientes", descricao="Gestão de clientes", ativo_por_padrao=True)

    def test_basic_fields(self):
        self.assertEqual(self.mod.nome, "Clientes")
        self.assertEqual(str(self.mod), "Clientes")
        self.assertTrue(self.mod.ativo_por_padrao)


class TestTenantModulesIntegration(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa B", subdomain="empresa-b")

    def test_assign_and_check_modules_legacy_dict(self):
        cfg = {"clientes": {"enabled": True}, "produtos": {"enabled": False}}
        self.tenant.modules = cfg
        self.tenant.save()
        self.assertTrue(self.tenant.has_module("clientes"))
        self.assertFalse(self.tenant.has_module("produtos"))
        self.assertTrue(self.tenant.has_module("core"))

    def test_assign_and_check_modules_list_format(self):
        cfg = {"modules": ["estoque", "financeiro"]}
        self.tenant.modules = cfg
        self.tenant.save()
        self.assertTrue(self.tenant.has_module("estoque"))
        self.assertFalse(self.tenant.has_module("clientes"))


class TestTenantMiddleware(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="ACorp", subdomain="acorp")
        self.t2 = Tenant.objects.create(name="BCorp", subdomain="bcorp")
        User = get_user_model()
        self.user = User.objects.create_user(username="bob", password="x")
        role_admin = Role.objects.create(tenant=self.t1, name="admin")
        role_user = Role.objects.create(tenant=self.t2, name="user")
        TenantUser.objects.create(tenant=self.t1, user=self.user, role=role_admin, is_tenant_admin=True)
        TenantUser.objects.create(tenant=self.t2, user=self.user, role=role_user, is_tenant_admin=False)

    def test_middleware_resolution(self):
        from django.http import HttpRequest

        from core.middleware import TenantMiddleware

        mw = TenantMiddleware(lambda r: None)

        req = HttpRequest()
        req.META["HTTP_HOST"] = "acorp.example.com"
        req.user = self.user
        mw.process_request(req)
        self.assertEqual(getattr(req, "tenant", None), self.t1)

        req2 = HttpRequest()
        req2.META["HTTP_X_TENANT"] = "bcorp"
        req2.user = self.user
        mw.process_request(req2)
        self.assertEqual(getattr(req2, "tenant", None), self.t2)

        req3 = HttpRequest()
        req3.user = self.user
        mw.process_request(req3)
        self.assertFalse(hasattr(req3, "tenant"))

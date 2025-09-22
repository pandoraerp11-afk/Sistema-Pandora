import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template

from core.authorization import REASON_MODULE_DISABLED, REASON_PORTAL_DENY, can_access_module
from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
class TestAuthorizationAccess:
    @pytest.fixture
    def tenant(self):
        # Formato tolerado pelo método is_module_enabled: dict com chave "modules"
        return Tenant.objects.create(
            name="Empresa X", slug="empresa-x", enabled_modules={"modules": ["clientes", "documentos"]}
        )

    @pytest.fixture
    def user_interno(self):
        return User.objects.create_user(username="interno", password="x", user_type="INTERNAL")

    @pytest.fixture
    def user_portal(self):
        # Usuário portal usando campo canônico user_type
        user = User.objects.create_user(
            username="portaluser",
            password="x",
            user_type="PORTAL",
        )
        return user

    @pytest.fixture
    def bind_users(self, tenant, user_interno, user_portal):
        TenantUser.objects.create(tenant=tenant, user=user_interno, is_tenant_admin=False)
        TenantUser.objects.create(tenant=tenant, user=user_portal, is_tenant_admin=False)

    def test_interno_module_enabled(self, tenant, user_interno, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_interno, tenant, "clientes")
        assert decision.allowed is True

    def test_portal_whitelist_allowed(self, tenant, user_portal, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_portal, tenant, "documentos")
        assert decision.allowed is True

    def test_portal_denied_non_whitelisted(self, tenant, user_portal, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_portal, tenant, "clientes")
        assert decision.allowed is False
        assert decision.reason == REASON_PORTAL_DENY

    def test_module_disabled(self, tenant, user_interno, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_interno, tenant, "financeiro")
        assert decision.allowed is False
        assert decision.reason == REASON_MODULE_DISABLED

    def test_superuser_always_allowed(self, tenant, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        su = User.objects.create_superuser(username="root", password="x", email="root@example.com")
        decision = can_access_module(su, tenant, "clientes")
        assert decision.allowed is True

    def test_module_inexistente(self, tenant, user_interno, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_interno, tenant, "modulo_que_nao_existe")
        # Não está na lista do tenant => disabled
        assert decision.allowed is False
        assert decision.reason == REASON_MODULE_DISABLED

    def test_sem_tenant(self, user_interno, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos"]
        decision = can_access_module(user_interno, None, "clientes")
        assert decision.allowed is False

    def test_portal_only_whitelist_visible(self, tenant, user_portal, bind_users, settings):
        settings.PORTAL_ALLOWED_MODULES = ["documentos", "chat"]
        settings.FEATURE_UNIFIED_ACCESS = True
        settings.FEATURE_REMOVE_MENU_HARDCODE = True
        ok_decision = can_access_module(user_portal, tenant, "documentos")
        deny_decision = can_access_module(user_portal, tenant, "clientes")
        assert ok_decision.allowed is True
        assert deny_decision.allowed is False and deny_decision.reason == REASON_PORTAL_DENY

    def test_menu_render_portal_filters_modules(self, tenant, user_portal, bind_users, settings, rf):
        settings.PORTAL_ALLOWED_MODULES = ["chat"]
        settings.FEATURE_UNIFIED_ACCESS = True
        settings.FEATURE_REMOVE_MENU_HARDCODE = True
        tenant.enabled_modules = {"modules": ["chat", "clientes"]}
        tenant.save(update_fields=["enabled_modules"])
        request = rf.get("/alguma/url/")
        request.user = user_portal
        request.session = {}
        request.session["tenant_id"] = tenant.id
        tpl = Template("{% load menu_tags %}{% render_sidebar_menu %}")
        html = tpl.render(Context({"request": request}))
        assert ("Chat" in html) or ("chat" in html)
        assert "Clientes" not in html

    def test_menu_render_internal_sees_clientes(self, tenant, user_interno, bind_users, settings, rf):
        settings.PORTAL_ALLOWED_MODULES = ["chat"]
        settings.FEATURE_UNIFIED_ACCESS = True
        settings.FEATURE_REMOVE_MENU_HARDCODE = True
        tenant.enabled_modules = {"modules": ["chat", "clientes"]}
        tenant.save(update_fields=["enabled_modules"])
        request = rf.get("/alguma/url/")
        request.user = user_interno
        request.session = {}
        request.session["tenant_id"] = tenant.id
        tpl = Template("{% load menu_tags %}{% render_sidebar_menu %}")
        html = tpl.render(Context({"request": request}))
        assert "Clientes" in html

    def test_portal_403_headers(self, tenant, user_portal, bind_users, settings, client):
        """Portal user deve receber 403 com headers ao acessar módulo não whitelist quando flag 403 ativa."""
        settings.PORTAL_ALLOWED_MODULES = ["chat"]  # 'clientes' não permitido
        settings.FEATURE_UNIFIED_ACCESS = True
        settings.FEATURE_REMOVE_MENU_HARDCODE = True
        settings.FEATURE_MODULE_DENY_403 = True
        tenant.enabled_modules = {"modules": ["chat", "clientes"]}
        tenant.save(update_fields=["enabled_modules"])
        client.force_login(user_portal)
        session = client.session
        session["tenant_id"] = tenant.id
        session.save()
        resp = client.get("/clientes/")
        assert resp.status_code == 403
        assert resp["X-Deny-Reason"] == REASON_PORTAL_DENY
        assert resp["X-Deny-Module"] == "clientes"

    def test_modulo_desabilitado_retorna_denial(self, tenant, user_interno, bind_users, settings, client):
        """Garantir que módulo ausente em enabled_modules gera denial (sem bypass de TESTING)."""
        settings.FEATURE_UNIFIED_ACCESS = True
        settings.FEATURE_REMOVE_MENU_HARDCODE = True
        settings.FEATURE_MODULE_DENY_403 = True
        # Remover 'financeiro' e garantir que está fora
        tenant.enabled_modules = {"modules": ["clientes", "documentos"]}
        tenant.save(update_fields=["enabled_modules"])
        client.force_login(user_interno)
        session = client.session
        session["tenant_id"] = tenant.id
        session.save()
        resp = client.get("/financeiro/")
        assert resp.status_code in (302, 403)
        # Se 403 deve ter headers, se 302 deve apontar a dashboard
        if resp.status_code == 403:
            assert resp["X-Deny-Module"] == "financeiro"
        else:
            assert "/dashboard" in resp.headers.get("Location", "")

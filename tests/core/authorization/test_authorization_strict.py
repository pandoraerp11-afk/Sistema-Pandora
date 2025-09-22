import pytest
from django.contrib.auth import get_user_model

from core.authorization import REASON_MODULE_DISABLED, REASON_PORTAL_DENY, REASON_RESOLVER_DENY, can_access_module

User = get_user_model()


@pytest.mark.django_db
def test_portal_whitelist_denial(settings):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos"]
    user = User.objects.create_user("portalx", password="x")
    # Marcar como portal via atributo dinâmico e grupo para garantir detecção
    user.user_type = "PORTAL"
    from django.contrib.auth.models import Group

    grp, _ = Group.objects.get_or_create(name=getattr(settings, "PORTAL_USER_GROUP_NAME", "PortalUser"))
    user.groups.add(grp)
    user.save()
    from core.models import Tenant

    tenant = Tenant.objects.create(nome="T1", slug="t1", enabled_modules='["clientes","documentos"]')
    dec_ok = can_access_module(user, tenant, "documentos")
    dec_deny = can_access_module(user, tenant, "clientes")
    assert dec_ok.allowed is True
    assert dec_deny.allowed is False and dec_deny.reason == REASON_PORTAL_DENY


@pytest.mark.django_db
def test_permission_resolver_strict_enforces(settings, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    user = User.objects.create_user("interno", password="x")
    from core.models import Tenant

    tenant = Tenant.objects.create(nome="T2", slug="t2", enabled_modules='["clientes"]')
    # Monkeypatch permission_resolver to always deny
    from shared.services import permission_resolver as pr_mod

    class DummyResolver:
        def resolve(self, user, tenant, action_code):
            return False, "DENY"

    monkeypatch.setattr(pr_mod, "permission_resolver", DummyResolver())
    decision = can_access_module(user, tenant, "clientes")
    assert decision.allowed is False and decision.reason in {REASON_RESOLVER_DENY, REASON_MODULE_DISABLED}


@pytest.mark.django_db
def test_permission_resolver_strict_denies_module(settings):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    user = User.objects.create_user("interno2", password="x")
    from core.models import Tenant

    tenant = Tenant.objects.create(nome="T3", slug="t3", enabled_modules='["financeiro"]')
    # Sem permissões personalizadas, resolver deve negar VIEW_FINANCEIRO e módulo deve ser negado em modo estrito
    decision = can_access_module(user, tenant, "financeiro")
    assert decision.allowed is False and decision.reason in {REASON_RESOLVER_DENY, REASON_MODULE_DISABLED}

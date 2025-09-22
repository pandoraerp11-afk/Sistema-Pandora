import pytest
from django.contrib.auth import get_user_model

from core.authorization import REASON_OK, REASON_PORTAL_DENY, can_access_module
from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_portal_whitelist_allows_and_denies(settings):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos"]
    tenant = Tenant.objects.create(nome="T", slug="t", enabled_modules={"modules": ["documentos", "financeiro"]})
    u = User.objects.create_user("portaluser", password="x")
    # Marcar como portal
    u.user_type = "PORTAL"
    TenantUser.objects.create(tenant=tenant, user=u, is_tenant_admin=False)
    # Allowed
    dec_ok = can_access_module(u, tenant, "documentos")
    assert dec_ok.allowed and dec_ok.reason == REASON_OK
    # Denied (fora whitelist)
    dec_no = can_access_module(u, tenant, "financeiro")
    assert not dec_no.allowed and dec_no.reason == REASON_PORTAL_DENY


@pytest.mark.django_db
def test_non_portal_not_restricted_by_whitelist(settings):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos"]
    tenant = Tenant.objects.create(nome="T2", slug="t2", enabled_modules={"modules": ["documentos", "financeiro"]})
    u = User.objects.create_user("internal", password="x")
    TenantUser.objects.create(tenant=tenant, user=u, is_tenant_admin=False)
    dec_fin = can_access_module(u, tenant, "financeiro")
    assert dec_fin.allowed

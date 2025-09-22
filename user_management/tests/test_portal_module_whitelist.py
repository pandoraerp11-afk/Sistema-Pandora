import pytest
from django.contrib.auth import get_user_model

from core.authorization import REASON_PORTAL_DENY, can_access_module
from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_portal_denied_module_outside_whitelist(settings):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos"]
    tenant = Tenant.objects.create(nome="T3", slug="t3", enabled_modules={"modules": ["documentos", "financeiro"]})
    u = User.objects.create_user("portalw", password="x")
    u.user_type = "PORTAL"
    TenantUser.objects.create(tenant=tenant, user=u, is_tenant_admin=False)
    dec = can_access_module(u, tenant, "financeiro")
    assert not dec.allowed and dec.reason == REASON_PORTAL_DENY

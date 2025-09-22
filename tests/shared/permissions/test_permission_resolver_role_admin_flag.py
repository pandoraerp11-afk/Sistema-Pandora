import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import has_permission

pytestmark = [pytest.mark.django_db]


def test_role_admin_name_triggers_is_admin_flag():
    U = get_user_model()
    u = U.objects.create_user("roleflag", "r@example.com", "x")
    t = Tenant.objects.create(nome="Empresa RF", slug="emp-rf")
    TenantUser.objects.create(user=u, tenant=t)
    admin_role = Role.objects.create(tenant=t, name="Admin", description="Admin role implicit")
    tu = u.tenant_memberships.get(tenant=t)
    tu.role = admin_role
    tu.save(update_fields=["role"])
    assert has_permission(u, t, "CREATE_COTACAO") is True

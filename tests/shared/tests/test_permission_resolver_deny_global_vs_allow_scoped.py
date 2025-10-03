import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_deny_global_over_allow_scoped():
    tenant = Tenant.objects.create(name="Tperm6", subdomain="tperm6")
    u = User.objects.create_user("user6", password="x")
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    # Allow scoped (tenant) genérico
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=True, scope_tenant=tenant)
    # Deny global genérico
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=False)
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO")
    assert allowed is False, "Deny global deve prevalecer sobre allow scoped (peso deny +100 > allow +50)"

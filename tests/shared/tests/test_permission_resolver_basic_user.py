import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import has_permission
from user_management.models import PermissaoPersonalizada

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_basic_allow_and_deny_precedence():
    cache.clear()
    tenant = Tenant.objects.create(name="Empresa X", subdomain="emp-x")
    user = User.objects.create_user(username="u1", password="pass", email="u1@example.com")
    role = Role.objects.create(tenant=tenant, name="Basic")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)

    # Sem permissão personalizada -> False
    assert has_permission(user, tenant, "read_mod_sample") is False

    # Allow scoped -> True
    PermissaoPersonalizada.objects.create(
        user=user, modulo="mod_sample", acao="read", concedida=True, scope_tenant=tenant
    )
    assert has_permission(user, tenant, "read_mod_sample") is True

    # Add deny scoped mesma ação -> passa a False
    PermissaoPersonalizada.objects.create(
        user=user, modulo="mod_sample", acao="read", concedida=False, scope_tenant=tenant
    )
    assert has_permission(user, tenant, "read_mod_sample") is False


@pytest.mark.django_db
@pytest.mark.permission
def test_global_vs_scoped_order():
    cache.clear()
    tenant = Tenant.objects.create(name="Empresa Y", subdomain="emp-y")
    user = User.objects.create_user(username="u2", password="pass", email="u2@example.com")
    role = Role.objects.create(tenant=tenant, name="RoleY")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)

    assert has_permission(user, tenant, "view_dashboard") is False

    # Global allow
    PermissaoPersonalizada.objects.create(user=user, modulo="dashboard", acao="view", concedida=True)
    assert has_permission(user, tenant, "view_dashboard") is True

    # Scoped deny override
    PermissaoPersonalizada.objects.create(
        user=user, modulo="dashboard", acao="view", concedida=False, scope_tenant=tenant
    )
    assert has_permission(user, tenant, "view_dashboard") is False

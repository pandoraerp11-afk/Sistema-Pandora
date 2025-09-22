import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import has_permission, permission_resolver
from user_management.models import PermissaoPersonalizada

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def user_and_tenant(db):
    User = get_user_model()
    u = User.objects.create_user("permuser", "p@example.com", "x")
    t = Tenant.objects.create(nome="Empresa Perm", slug="emp-perm")
    TenantUser.objects.create(user=u, tenant=t)
    return u, t


@pytest.fixture
def role_admin(db, user_and_tenant):
    _, t = user_and_tenant
    return Role.objects.create(tenant=t, name="Admin", description="Admin test role")


@pytest.fixture
def role_basic(db, user_and_tenant):
    _, t = user_and_tenant
    return Role.objects.create(tenant=t, name="Basic", description="Basic test role")


def test_precedence_personalizada_deny_over_role(user_and_tenant, role_admin):
    u, t = user_and_tenant
    tu = u.tenant_memberships.get(tenant=t)
    tu.role = role_admin
    tu.save(update_fields=["role"])
    assert has_permission(u, t, "CREATE_COTACAO") is True  # via nome Admin (is_admin)
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=t, acao="create", modulo="cotacao", concedida=False)
    assert has_permission(u, t, "CREATE_COTACAO") is False


def test_cache_version_bump_invalidation(user_and_tenant, role_admin):
    u, t = user_and_tenant
    tu = u.tenant_memberships.get(tenant=t)
    tu.role = role_admin
    tu.save(update_fields=["role"])
    cache.clear()
    assert has_permission(u, t, "VIEW_COTACAO") is True
    # Rename role para remover implicit admin
    role_admin.name = "Guest"
    role_admin.save(update_fields=["name"])
    # Ainda True (cache quente)
    assert has_permission(u, t, "VIEW_COTACAO") is True
    permission_resolver.invalidate_cache(user_id=u.id, tenant_id=t.id)
    assert has_permission(u, t, "VIEW_COTACAO") is False


def test_stale_cache_after_permission_removed(user_and_tenant, role_admin):
    u, t = user_and_tenant
    tu = u.tenant_memberships.get(tenant=t)
    tu.role = role_admin
    tu.save(update_fields=["role"])
    cache.clear()
    assert has_permission(u, t, "CREATE_COTACAO") is True
    role_admin.name = "Guest"
    role_admin.save(update_fields=["name"])
    # Cache mantém allow
    assert has_permission(u, t, "CREATE_COTACAO") is True
    permission_resolver.invalidate_cache(user_id=u.id, tenant_id=t.id)
    assert has_permission(u, t, "CREATE_COTACAO") is False

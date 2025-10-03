import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser
from shared.services.ui_permissions import build_ui_permissions

pytestmark = [pytest.mark.django_db]

User = get_user_model()


@pytest.fixture
def tenant():
    return Tenant.objects.create(nome="Empresa X", slug="emp-x")


@pytest.fixture
def role_basic(tenant):
    return Role.objects.create(tenant=tenant, name="Basic", description="Basic role")


@pytest.fixture
def role_admin(tenant):
    return Role.objects.create(tenant=tenant, name="Admin", description="Admin role")


@pytest.fixture
def user_basic(role_basic, tenant):
    u = User.objects.create_user("basic_user")
    TenantUser.objects.create(user=u, tenant=tenant, role=role_basic)
    return u


@pytest.fixture
def user_admin(role_admin, tenant):
    u = User.objects.create_user("admin_user")
    TenantUser.objects.create(user=u, tenant=tenant, role=role_admin)
    return u


@pytest.mark.parametrize("module_key", ["PRODUTO", "SERVICO"])
def test_module_key_basic_has_no_crud(user_basic, tenant, module_key):
    perms = build_ui_permissions(user_basic, tenant, module_key=module_key)
    assert perms["can_view"] is False  # sem permissões ou admin implícito
    assert perms["can_add"] is False
    assert perms["can_edit"] is False
    assert perms["can_delete"] is False


@pytest.mark.parametrize("module_key", ["PRODUTO", "SERVICO"])
def test_module_key_admin_infers_allow(user_admin, tenant, module_key):
    perms = build_ui_permissions(user_admin, tenant, module_key=module_key)
    assert perms["can_view"] is True
    assert perms["can_add"] is True
    assert perms["can_edit"] is True
    assert perms["can_delete"] is True


@pytest.mark.parametrize("module_key", ["PRODUTO", "SERVICO"])
def test_module_key_superuser_short_circuit(tenant, module_key):
    su = User.objects.create_superuser("root", "root@example.com", "x")
    perms = build_ui_permissions(su, tenant, module_key=module_key)
    assert perms["can_view"] and perms["can_add"] and perms["can_edit"] and perms["can_delete"]

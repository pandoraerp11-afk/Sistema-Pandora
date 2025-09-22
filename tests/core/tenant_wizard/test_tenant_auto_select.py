import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_auto_select_single_tenant_session(client):
    """Ao fazer login com um único TenantUser, o conftest deve injetar tenant_id na sessão."""
    User = get_user_model()
    u = User.objects.create_user("only", "only@example.com", "x")
    from core.models import Tenant, TenantUser

    t = Tenant.objects.create(name="Empresa Only", subdomain="only")
    TenantUser.objects.create(user=u, tenant=t)
    assert "tenant_id" not in client.session
    client.force_login(u)
    # patch em force_login deve ter setado
    assert client.session.get("tenant_id") == t.id


@pytest.mark.django_db
def test_no_auto_select_when_multiple(client):
    """Se usuário tem >1 tenants não escolhe automaticamente para evitar ambiguidade."""
    User = get_user_model()
    u = User.objects.create_user("multi", "multi@example.com", "x")
    from core.models import Tenant, TenantUser

    t1 = Tenant.objects.create(name="Empresa A", subdomain="a")
    t2 = Tenant.objects.create(name="Empresa B", subdomain="b")
    TenantUser.objects.create(user=u, tenant=t1)
    TenantUser.objects.create(user=u, tenant=t2)
    client.force_login(u)
    assert client.session.get("tenant_id") is None


@pytest.mark.django_db
def test_wizard_create_first_get_status_ok(client):
    """GET em tenant_create deve responder 200 (sem redirects extras) quando autenticado."""
    User = get_user_model()
    u = User.objects.create_superuser("admin2", "admin2@example.com", "x")
    from core.models import Role, Tenant, TenantUser

    # criar tenant + role para vínculo; auto enable modules via fixture
    base = Tenant.objects.create(name="Empresa Base 2", subdomain="base2")
    role = Role.objects.create(tenant=base, name="Owner")
    TenantUser.objects.create(user=u, tenant=base, role=role, is_tenant_admin=True)
    client.force_login(u)
    url = reverse("core:tenant_create")
    r = client.get(url)
    assert r.status_code == 200

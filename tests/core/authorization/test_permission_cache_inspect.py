import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_permission_cache_inspect_requires_superuser(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="CI", slug="ci", enabled_modules={"modules": ["clientes"]})
    u = User.objects.create_user("normal", password="x")
    TenantUser.objects.create(tenant=tenant, user=u)
    client.force_login(u)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()
    resp = client.get("/core/api/permissions/cache/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_permission_cache_inspect_superuser_ok(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    from core.models import Tenant

    tenant = Tenant.objects.create(nome="CJ", slug="cj", enabled_modules={"modules": ["clientes", "financeiro"]})
    su = User.objects.create_superuser("sup", "s@x.com", "x")
    client.force_login(su)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()
    resp = client.get("/core/api/permissions/cache/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tenant.id
    assert "version" in data and "potential_keys" in data and len(data["potential_keys"]) >= 1

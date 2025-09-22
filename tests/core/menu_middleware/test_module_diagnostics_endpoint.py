import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_module_diagnostics_basic(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="DX", slug="dx", enabled_modules={"modules": ["clientes", "financeiro"]})
    user = User.objects.create_user("diag", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()
    resp = client.get("/core/api/modules/diagnostics/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tenant.id
    mods = {m["module"]: m for m in data["modules"]}
    assert "clientes" in mods and "financeiro" in mods
    assert mods["clientes"]["enabled_for_tenant"] is True


@pytest.mark.django_db
def test_module_diagnostics_superuser_sees_all(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    from core.models import Tenant

    tenant = Tenant.objects.create(nome="DY", slug="dy", enabled_modules={"modules": ["clientes"]})
    superuser = User.objects.create_superuser("superdiag", "s@example.com", "x")
    client.force_login(superuser)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()
    resp = client.get("/core/api/modules/diagnostics/")
    assert resp.status_code == 200
    data = resp.json()
    # Como superuser, lista deve conter pelo menos módulos base conhecidos
    assert data["count"] >= len(data["modules"]) and data["count"] == len(data["modules"])
    assert any(m["module"] == "clientes" for m in data["modules"])

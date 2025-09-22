import pytest
from django.contrib.auth import get_user_model

from shared.services.permission_resolver import permission_resolver

pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def _make_tenant():
    from core.models import Tenant

    try:
        return Tenant.objects.create(name="TxImp", subdomain="tximp")
    except Exception:
        return Tenant.objects.create(nome="TxImp", slug="tximp")


def _membership(user, tenant):
    from core.models import TenantUser

    TenantUser.objects.create(user=user, tenant=tenant)


def test_implicit_pipeline_branch(monkeypatch):
    # Ação não está no action_map -> pula role e cai em implicit
    User = get_user_model()
    u = User.objects.create_user("impluser", password="x", is_active=True)
    tenant = _make_tenant()
    _membership(u, tenant)

    def fake_check(user, tenant, action, context):
        return True, "Acesso fornecedor simulado"

    monkeypatch.setattr(permission_resolver, "_check_implicit_roles", fake_check)
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_DASHBOARD_CLIENTE")
    assert allowed is True
    assert "Acesso fornecedor" in reason or "Acesso" in reason

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def _make_tenant():
    from core.models import Tenant

    # Tentar campos alternativos conforme modelo
    try:
        return Tenant.objects.create(name="TxPerm", subdomain="txperm")
    except Exception:
        return Tenant.objects.create(nome="TxPerm", slug="txperm")


def _membership(user, tenant):
    from core.models import TenantUser

    TenantUser.objects.create(user=user, tenant=tenant)


def test_personalizada_deny_precedence():
    User = get_user_model()
    u = User.objects.create_user("permdeny", password="x", is_active=True)
    tenant = _make_tenant()
    _membership(u, tenant)
    # Allow + Deny mesma ação -> Deny vence (maior score)
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=tenant, modulo="cotacao", acao="create", concedida=True)
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=tenant, modulo="cotacao", acao="create", concedida=False)
    allowed, reason = permission_resolver.resolve(u, tenant, "CREATE_COTACAO")
    assert allowed is False
    assert "Permissão personalizada" in reason


def test_personalizada_expired_deny_ignored():
    User = get_user_model()
    u = User.objects.create_user("permexp", password="x", is_active=True)
    tenant = _make_tenant()
    _membership(u, tenant)
    past = timezone.now() - timezone.timedelta(days=1)
    PermissaoPersonalizada.objects.create(
        user=u, scope_tenant=tenant, modulo="cotacao", acao="create", concedida=False, data_expiracao=past
    )
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=tenant, modulo="cotacao", acao="create", concedida=True)
    allowed, reason = permission_resolver.resolve(u, tenant, "CREATE_COTACAO")
    assert allowed is True
    assert "Permissão personalizada" in reason

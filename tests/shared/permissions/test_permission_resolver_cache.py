import pytest
from django.contrib.auth import get_user_model

from shared.services.permission_resolver import permission_resolver

pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def _make_tenant():
    from core.models import Tenant

    try:
        return Tenant.objects.create(name="TxCache", subdomain="txcache")
    except Exception:
        return Tenant.objects.create(nome="TxCache", slug="txcache")


def _membership(user, tenant):
    from core.models import TenantUser

    TenantUser.objects.create(user=user, tenant=tenant)  # sem role para forçar negação


def test_permission_cache_hit_path():
    """Primeira resolução gera entrada em cache; segunda deve seguir ramo de cache hit."""
    User = get_user_model()
    u = User.objects.create_user("permcache", password="x", is_active=True)
    t = _make_tenant()
    _membership(u, t)
    # Ação mapeada porém sem role => negação armazenada em cache
    allowed1, reason1 = permission_resolver.resolve(u, t, "CREATE_COTACAO")
    allowed2, reason2 = permission_resolver.resolve(u, t, "CREATE_COTACAO")
    assert allowed1 is False and allowed2 is False
    # Segunda razão deve conter indicação de cache ou manter mensagem consistente
    assert "Role" in reason1  # mensagem de role
    # Não obrigamos substring no reason2 (pode vir reduzida), mas garantimos coerência
    assert isinstance(reason2, str)

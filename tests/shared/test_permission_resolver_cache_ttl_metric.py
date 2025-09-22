import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_permission_resolver_cache_ttl_metric(settings):
    """Garante que o histograma de TTL não quebra e é observável em hits."""
    settings.PERMISSION_RESOLVER_TRACE = True
    from core.models import Role, Tenant, TenantUser
    from shared.services.permission_resolver import permission_resolver

    user = User.objects.create(username="ttl", is_active=True)
    tenant = Tenant.objects.create(name="TT", slug="tt")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Primeira chamada (miss)
    permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    # Segunda (hit) — deve tentar observar TTL, teste apenas garante que não lança
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    assert isinstance(allowed2, bool)
    assert "cache_hit" in reason2

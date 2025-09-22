import pytest
from django.contrib.auth import get_user_model

from shared.services.permission_resolver import permission_resolver

User = get_user_model()


@pytest.mark.django_db
def test_permission_resolver_cache_hit_trace(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    from core.models import Role, Tenant, TenantUser

    user = User.objects.create(username="cacheu", is_active=True)
    tenant = Tenant.objects.create(name="TT", slug="tt")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Primeira chamada gera cache
    allowed1, reason1 = permission_resolver.resolve(user, tenant, "UNKNOWN_ACTION")
    assert allowed1 is False
    # Segunda deve ter cache_hit no trace
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "UNKNOWN_ACTION")
    assert allowed2 is False
    assert "cache_hit" in reason2

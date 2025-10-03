"""Migrado de shared/tests/test_permission_resolver_cache_version.py."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_cache_version_increments_on_permission_change(settings):
    from user_management.models import PermissaoPersonalizada

    cache.clear()
    tenant = Tenant.objects.create(name="Tcachev", subdomain="tcachev")
    user = User.objects.create_user("cachevuser", password="x")
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    allowed0, reason0 = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    key_before = permission_resolver._get_cache_key(user.id, tenant.id, "VIEW_FINANCEIRO")
    version_before = key_before.split(":")[1]

    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="financeiro",
        acao="view",
        concedida=True,
        scope_tenant=tenant,
    )
    allowed1, reason1 = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    key_after = permission_resolver._get_cache_key(user.id, tenant.id, "VIEW_FINANCEIRO")
    version_after = key_after.split(":")[1]

    assert version_after >= version_before
    assert allowed1 is True

    PermissaoPersonalizada.objects.all().delete()
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    key_after2 = permission_resolver._get_cache_key(user.id, tenant.id, "VIEW_FINANCEIRO")
    version_after2 = key_after2.split(":")[1]

    assert int(version_after2) >= int(version_after)
    assert allowed2 is False

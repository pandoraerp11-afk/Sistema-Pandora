import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def test_cache_hit_trace(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_cache1", password="x")
    tenant = Tenant.objects.create(name="Tcache1", subdomain="tcache1")
    TenantUser.objects.create(user=user, tenant=tenant)
    cache.clear()
    # primeira chamada -> miss
    dec1 = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec1.trace is not None and "default_result" in dec1.trace
    # segunda chamada -> hit
    dec2 = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec2.trace is not None and "cache_hit" in dec2.trace
    # source pode vir como cache
    assert dec2.source in {"cache", "default"}


def test_pipeline_role_allow(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_role1", password="x")
    tenant = Tenant.objects.create(name="Trole1", subdomain="trole1")
    role = Role.objects.create(tenant=tenant, name="ADMIN")
    TenantUser.objects.create(user=user, tenant=tenant, role=role)
    dec = permission_resolver.resolve_decision(user, tenant, "CREATE_COTACAO")
    assert dec.allowed is True
    assert dec.source in {"role", "cache"}
    assert dec.trace and ("role_allow" in dec.trace or "cache_hit" in dec.trace)


def test_pipeline_default_negative(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_def1", password="x")
    tenant = Tenant.objects.create(name="Tdef1", subdomain="tdef1")
    TenantUser.objects.create(user=user, tenant=tenant)
    dec = permission_resolver.resolve_decision(user, tenant, "ACTION_INEXISTENTE")
    assert dec.allowed is False
    # Como action não está no mapa, pipeline vai implicit->default e deve negar
    assert dec.trace and "default_result" in dec.trace

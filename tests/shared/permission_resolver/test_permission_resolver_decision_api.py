"""Migrado de shared/tests/test_permission_resolver_decision_api.py."""

import pytest
from django.contrib.auth import get_user_model

from core.models import Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def test_resolve_decision_trace_disabled(settings):
    settings.PERMISSION_RESOLVER_TRACE = False
    user = User.objects.create_user("u_decision1", password="x")
    tenant = Tenant.objects.create(name="Tdec1", subdomain="tdec1")
    TenantUser.objects.create(user=user, tenant=tenant)
    dec = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec.allowed is False
    assert dec.trace is None


def test_resolve_decision_trace_enabled(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_decision2", password="x")
    tenant = Tenant.objects.create(name="Tdec2", subdomain="tdec2")
    TenantUser.objects.create(user=user, tenant=tenant)
    dec = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec.allowed is False
    assert dec.trace is not None
    assert ("default_result" in dec.trace) or ("cache_hit" in dec.trace)
    assert dec.source in {None, "default", "cache"}


@pytest.mark.django_db
@pytest.mark.permission
def test_resolve_decision_source_personalizada(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    from user_management.models import PermissaoPersonalizada

    user = User.objects.create_user("u_decision3", password="x")
    tenant = Tenant.objects.create(name="Tdec3", subdomain="tdec3")
    TenantUser.objects.create(user=user, tenant=tenant)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="financeiro",
        acao="view",
        concedida=True,
        scope_tenant=tenant,
    )
    dec = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec.allowed is True
    assert dec.source in {"personalizada", "default", "role"}
    assert dec.trace and "personalizada" in dec.trace

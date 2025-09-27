"""Migrado de shared/tests/test_permission_resolver_precedence_variants.py."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

pytestmark = [pytest.mark.permission]
User = get_user_model()


@pytest.mark.django_db
def test_precedence_deny_scoped_resource_over_allow_global():
    user = User.objects.create_user("u_prec", password="x")
    tenant = Tenant.objects.create(name="T1", subdomain="t1")
    TenantUser.objects.create(user=user, tenant=tenant)
    PermissaoPersonalizada.objects.create(user=user, concedida=True, acao="view", modulo="financeiro")
    PermissaoPersonalizada.objects.create(
        user=user,
        concedida=True,
        acao="view",
        modulo="financeiro",
        recurso="doc:A",
    )
    PermissaoPersonalizada.objects.create(
        user=user,
        concedida=False,
        acao="view",
        modulo="financeiro",
        recurso="doc:A",
        scope_tenant=tenant,
    )
    allowed_A, reason_A = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO", resource="doc:A")
    assert allowed_A is False, reason_A
    allowed_B, reason_B = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO", resource="doc:B")
    assert allowed_B is True, reason_B


@pytest.mark.django_db
def test_precedence_expiration_filters_out_expired():
    user = User.objects.create_user("u_exp", password="x")
    tenant = Tenant.objects.create(name="T2", subdomain="t2")
    TenantUser.objects.create(user=user, tenant=tenant)
    PermissaoPersonalizada.objects.create(
        user=user,
        concedida=False,
        acao="view",
        modulo="financeiro",
        scope_tenant=tenant,
        data_expiracao=timezone.now() - timedelta(days=1),
    )
    PermissaoPersonalizada.objects.create(
        user=user,
        concedida=True,
        acao="view",
        modulo="financeiro",
        scope_tenant=tenant,
        data_expiracao=timezone.now() + timedelta(days=1),
    )
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    assert allowed is True, reason


@pytest.mark.django_db
def test_role_fallback_after_no_personal_permissions():
    user = User.objects.create_user("u_role", password="x")
    tenant = Tenant.objects.create(name="T3", subdomain="t3")
    tu = TenantUser.objects.create(user=user, tenant=tenant)
    role = Role.objects.create(tenant=tenant, name="ADMIN")
    role.can_view_cotacao = True  # type: ignore[attr-defined]
    role.save()
    tu.role = role
    tu.save(update_fields=["role"])
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    assert allowed is True, reason


@pytest.mark.django_db
def test_cache_invalidation_on_personal_permission_change():
    from django.core.cache import cache

    cache.clear()
    user = User.objects.create_user("u_cache", password="x")
    tenant = Tenant.objects.create(name="T4", subdomain="t4")
    TenantUser.objects.create(user=user, tenant=tenant)
    allowed1, reason1 = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    assert allowed1 is False
    PermissaoPersonalizada.objects.create(
        user=user,
        concedida=True,
        acao="view",
        modulo="financeiro",
        scope_tenant=tenant,
    )
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    assert allowed2 is True, reason2

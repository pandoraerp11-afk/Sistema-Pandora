"""Testes de snapshot/traço do PermissionResolver.

Mantido no nível direto de tests/shared para evitar avisos INP001 sobre
namespace implícito em subpastas.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import CustomUser, Role, Tenant, TenantUser
from shared.services.permission_resolver import PermissionResolver

PermissaoPersonalizada: Any
try:  # pragma: no cover
    from user_management.models import PermissaoPersonalizada as _PermissaoPersonalizada

    PermissaoPersonalizada = _PermissaoPersonalizada
except ImportError:  # pragma: no cover
    PermissaoPersonalizada = None

pytestmark = pytest.mark.django_db


def _trace_lines(resolver: PermissionResolver) -> list[str]:  # Compat: mantido nome antigo
    # Agora delega ao método público get_last_trace_lines()
    return resolver.get_last_trace_lines()


@pytest.fixture(name="resolver")
def fx_resolver() -> PermissionResolver:
    """Instancia resolver isolado."""
    return PermissionResolver()


@pytest.fixture(name="tenant")
def fx_tenant() -> Tenant:
    """Cria tenant simples usado nos cenários."""
    return Tenant.objects.create(name="T Perm", subdomain="tperm", enabled_modules={"modules": []})


@pytest.fixture(name="user_with_role")
def fx_user_with_role(tenant: Tenant) -> CustomUser:
    """Retorna usuário com role ADMIN (cobre token is_admin)."""
    user_model = get_user_model()
    user = cast(
        "CustomUser",
        user_model.objects.create_user(username="u_role", password="x"),  # noqa: S106
    )
    role = Role.objects.create(tenant=tenant, name="ADMIN")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    return user


@pytest.fixture(name="plain_user")
def fx_plain_user(tenant: Tenant) -> CustomUser:
    """Retorna usuário sem role (caminho default)."""
    user_model = get_user_model()
    user = cast(
        "CustomUser",
        user_model.objects.create_user(username="u_plain", password="x"),  # noqa: S106
    )
    TenantUser.objects.create(tenant=tenant, user=user)
    return user


def test_trace_role_allow(resolver: PermissionResolver, tenant: Tenant, user_with_role: CustomUser) -> None:
    """Verifica traço com explain primeiro (gera trace) e depois cache hit."""
    decision = resolver.explain_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    # Segundo caminho: cache
    allowed_cached = resolver.has_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert allowed_cached is True  # noqa: S101
    trace = _trace_lines(resolver)
    cache_hit = any("cache_hit" in line for line in trace)
    assert cache_hit or any("role" in line for line in trace)  # noqa: S101


def test_trace_default_result(resolver: PermissionResolver, tenant: Tenant, plain_user: CustomUser) -> None:
    """Verifica presença de default_result para ação desconhecida."""
    decision = resolver.explain_permission(plain_user, tenant, "UNKNOWN_ACTION_XYZ", _force_trace=True)
    assert decision.allowed is False  # noqa: S101
    assert any("default_result" in line for line in resolver.get_last_trace_lines())  # noqa: S101


def test_personalizada_override(resolver: PermissionResolver, tenant: Tenant, plain_user: CustomUser) -> None:
    """Garante marcador 'personalizada' com modelo atual (modulo/acao)."""
    if PermissaoPersonalizada is None:
        pytest.skip("Modelo PermissaoPersonalizada indisponível")
    perm = PermissaoPersonalizada.objects.create(
        user=plain_user,
        modulo="produto",
        acao="VIEW",
        concedida=True,
        scope_tenant=tenant,
    )
    decision = resolver.explain_permission(plain_user, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    assert any("personalizada" in line for line in resolver.get_last_trace_lines())  # noqa: S101
    # Chamada subsequente cacheada
    assert resolver.has_permission(plain_user, tenant, "VIEW_PRODUTO", _force_trace=True) is True  # noqa: S101
    perm.delete()
    cache.clear()

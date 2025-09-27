"""Testes de snapshot/traço do PermissionResolver.

Objetivo: garantir estabilidade de passos principais de decisão sem acoplar
demais a implementação interna. Acessos a atributos privados são aceitáveis
em contexto de teste. (Duplicado do teste consolidado em tests/shared.)

Nota: Mantido enquanto houver referência direta a este caminho; pode ser
removido após confirmar que o teste consolidado substitui este.
"""  # ruff: noqa: INP001

from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import CustomUser, Role, Tenant, TenantUser
from shared.services.permission_resolver import PermissionResolver

# Import opcional do app user_management sem usar type: ignore desnecessário.
PermissaoPersonalizada: Any
try:  # pragma: no cover - ambiente pode não ter app
    from user_management.models import (
        PermissaoPersonalizada as _PermissaoPersonalizada,
    )

    PermissaoPersonalizada = _PermissaoPersonalizada
except ImportError:  # pragma: no cover
    PermissaoPersonalizada = None

pytestmark = pytest.mark.django_db


def _trace_lines(resolver: PermissionResolver) -> list[str]:
    """Retorna linhas de trace de forma resiliente.

    Usa getattr para não falhar caso o atributo privado mude futuramente.
    """
    return list(getattr(resolver, "_last_trace_lines", []))


@pytest.fixture(name="resolver")
def fx_resolver() -> PermissionResolver:
    """Instancia um PermissionResolver isolado para cada teste."""
    return PermissionResolver()


@pytest.fixture(name="tenant")
def fx_tenant() -> Tenant:
    """Cria tenant simples usado pelos cenários."""
    return Tenant.objects.create(name="T Perm", subdomain="tperm", enabled_modules={"modules": []})


@pytest.fixture(name="user_with_role")
def fx_user_with_role(tenant: Tenant) -> CustomUser:
    """Retorna usuário com role ADMIN (para acionar token is_admin)."""
    user_model = get_user_model()
    user = cast(
        "CustomUser",
        user_model.objects.create_user(
            username="u_role",
            password="x",  # noqa: S106 (test password)
        ),
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
        user_model.objects.create_user(
            username="u_plain",
            password="x",  # noqa: S106 (test password)
        ),
    )
    TenantUser.objects.create(tenant=tenant, user=user)  # sem role
    return user


def test_trace_role_allow(resolver: PermissionResolver, tenant: Tenant, user_with_role: CustomUser) -> None:
    """Verifica traço de caminho de allow via role com explain primeiro (gera marcador)."""
    decision = resolver.explain_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    # Segunda chamada deve bater cache
    allowed_cached = resolver.has_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert allowed_cached is True  # noqa: S101
    trace = _trace_lines(resolver)
    cache_hit = any("cache_hit" in line for line in trace)
    assert cache_hit or any("role" in line for line in trace)  # noqa: S101


def test_trace_default_result(resolver: PermissionResolver, tenant: Tenant, plain_user: CustomUser) -> None:
    """Verifica traço contendo default_result para ação desconhecida."""
    action = "UNKNOWN_ACTION_XYZ"
    decision = resolver.explain_permission(plain_user, tenant, action, _force_trace=True)
    assert decision.allowed is False  # noqa: S101
    assert any("default_result" in line for line in _trace_lines(resolver))  # noqa: S101


def test_personalizada_override(resolver: PermissionResolver, tenant: Tenant, plain_user: CustomUser) -> None:
    """Garante que permissão personalizada (modelo atual) gera marcador no trace."""
    if PermissaoPersonalizada is None:
        pytest.skip("Modelo PermissaoPersonalizada indisponível")

    # Modelo atual usa campos user/modulo/acao/scope_tenant
    perm = PermissaoPersonalizada.objects.create(
        user=plain_user,
        modulo="produto",
        acao="VIEW",
        concedida=True,
        scope_tenant=tenant,
    )
    decision = resolver.explain_permission(plain_user, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    assert any("personalizada" in line for line in _trace_lines(resolver))  # noqa: S101
    # Chamada subsequente (cache) ainda retorna allow
    assert resolver.has_permission(plain_user, tenant, "VIEW_PRODUTO", _force_trace=True) is True  # noqa: S101
    perm.delete()
    cache.clear()

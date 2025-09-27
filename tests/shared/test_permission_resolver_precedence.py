"""Testes de precedência de permissões personalizadas vs role e default.

Itens A-D:
 A. Personalized deny tem precedência sobre personalized allow e sobre role allow.
 B. Personalized allow permite quando não há deny aplicável e não há role permitindo.
 C. Role allow permite quando não há personalized deny/allow específica.
 D. Default deny ocorre quando não há role nem personalized aplicável.

Hierarquia (maior precedência primeiro): personalized deny > personalized allow > role > default.

Action map já inclui "VIEW_PRODUTO"; para o modelo usamos modulo="produto" e acao="VIEW".
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, cast

import pytest
from django.contrib.auth import get_user_model

from core.models import CustomUser, Role, Tenant, TenantUser
from shared.services.permission_resolver import PermissionResolver

pytestmark = pytest.mark.django_db


@pytest.fixture(name="tenant")
def fx_tenant() -> Tenant:
    """Cria tenant simples para os cenários de precedência."""
    return Tenant.objects.create(name="TPrec", subdomain="tprec", enabled_modules={"modules": []})


@pytest.fixture(name="user_base")
def fx_user_base(tenant: Tenant) -> CustomUser:
    """Usuário sem role para testar caminhos sem role."""
    user_model = get_user_model()
    user = cast("CustomUser", user_model.objects.create_user(username="u_prec_base", password="x"))  # noqa: S106
    TenantUser.objects.create(tenant=tenant, user=user)  # sem role
    return user


@pytest.fixture(name="user_with_role")
def fx_user_with_role(tenant: Tenant) -> CustomUser:
    """Usuário com role ADMIN (token is_admin garante allow)."""
    user_model = get_user_model()
    user = cast("CustomUser", user_model.objects.create_user(username="u_prec_role", password="x"))  # noqa: S106
    role = Role.objects.create(tenant=tenant, name="ADMIN")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    return user


@pytest.fixture(name="resolver")
def fx_resolver() -> PermissionResolver:
    """Instancia um resolver isolado por teste."""
    return PermissionResolver()


if TYPE_CHECKING:  # pragma: no cover
    from user_management.models import PermissaoPersonalizada as PermissaoPersonalizadaModel
else:  # pragma: no cover
    PermissaoPersonalizadaModel = object  # type: ignore[misc,assignment]


def _create_perm(
    user: CustomUser,
    tenant: Tenant,
    *,
    concedida: bool,
    recurso: str | None = None,
) -> PermissaoPersonalizadaModel:
    """Cria permissão personalizada auxiliar e retorna a instância."""
    from user_management.models import PermissaoPersonalizada  # noqa: PLC0415

    return PermissaoPersonalizada.objects.create(
        user=user,
        modulo="produto",
        acao="VIEW",
        concedida=concedida,
        scope_tenant=tenant,
        recurso=recurso,
    )


# A. Personalized deny > personalized allow > role
@pytest.mark.usefixtures("resolver")
def test_precedencia_personalized_deny_sobre_role_e_allow(tenant: Tenant, user_with_role) -> None:  # noqa: ANN001
    """Deny personalizado deve negar mesmo havendo allow personalizado ou role allow."""
    try:
        if importlib.util.find_spec("user_management.models") is None:  # pragma: no cover - ambiente sem app
            pytest.skip("Modelo PermissaoPersonalizada indisponível")
    except ImportError:  # pragma: no cover
        pytest.skip("Ambiente sem user_management (ImportError)")

    perm_allow = _create_perm(user_with_role, tenant, concedida=True)
    perm_deny = _create_perm(user_with_role, tenant, concedida=False)

    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_with_role.id, tenant_id=tenant.id)
    decision = resolver.explain_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is False  # noqa: S101
    assert decision.source == "personalizada"  # noqa: S101
    # Não verificar trace depois do cache overwrite
    assert resolver.has_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True) is False  # noqa: S101

    perm_allow.delete()
    perm_deny.delete()


# B. Personalized allow (sem deny) permite mesmo sem role
@pytest.mark.usefixtures("resolver")
def test_precedencia_personalized_allow_sem_deny_sem_role(tenant: Tenant, user_base) -> None:  # noqa: ANN001
    """Allow personalizado deve permitir quando isolado (sem deny e sem role)."""
    try:
        if importlib.util.find_spec("user_management.models") is None:  # pragma: no cover
            pytest.skip("Modelo PermissaoPersonalizada indisponível")
    except ImportError:  # pragma: no cover
        pytest.skip("Ambiente sem user_management (ImportError)")

    perm_allow = _create_perm(user_base, tenant, concedida=True)
    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_base.id, tenant_id=tenant.id)
    decision = resolver.explain_permission(user_base, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    assert decision.source == "personalizada"  # noqa: S101
    assert resolver.has_permission(user_base, tenant, "VIEW_PRODUTO", _force_trace=True) is True  # noqa: S101
    perm_allow.delete()


# C. Role allow quando não há personalized
@pytest.mark.usefixtures("resolver")
def test_precedencia_role_allow_sem_personalized(tenant: Tenant, user_with_role) -> None:  # noqa: ANN001
    """Role allow quando não existem permissões personalizadas."""
    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_with_role.id, tenant_id=tenant.id)
    decision = resolver.explain_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is True  # noqa: S101
    assert decision.source == "role"  # noqa: S101
    assert resolver.has_permission(user_with_role, tenant, "VIEW_PRODUTO", _force_trace=True) is True  # noqa: S101
    lines = resolver.get_last_trace_lines()
    assert any("role" in line or "cache" in line for line in lines)  # noqa: S101


# D. Default deny sem role e sem personalized
@pytest.mark.usefixtures("resolver")
def test_precedencia_default_deny(tenant: Tenant, user_base) -> None:  # noqa: ANN001
    """Default deny quando não há role ou personalized aplicável."""
    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_base.id, tenant_id=tenant.id)
    decision = resolver.explain_permission(user_base, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is False  # noqa: S101
    # Fonte pode ser 'role' (negação precoce por ausência de role ou role sem perm) ou 'default'
    assert decision.source in {"role", "default"}  # noqa: S101
    trace_lines = resolver.get_last_trace_lines()
    if decision.source == "default":
        assert any("default_result" in line for line in trace_lines)  # noqa: S101
    else:
        # Para negação via role não exigimos marcador 'default_result'
        assert not any("default_result" in line for line in trace_lines)  # noqa: S101
    assert resolver.has_permission(user_base, tenant, "VIEW_PRODUTO", _force_trace=True) is False  # noqa: S101

"""Testes adicionais de precedência envolvendo recurso específico.

Cenários:
1. Personalized deny global vs personalized allow recurso-específico -> deny deve prevalecer.
2. Personalized allow recurso-específico sem deny -> allow.

Reutiliza action VIEW_PRODUTO (modulo produto / acao VIEW).
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, cast

import pytest
from django.contrib.auth import get_user_model

from core.models import CustomUser, Role, Tenant, TenantUser

if TYPE_CHECKING:  # pragma: no cover
    from user_management.models import PermissaoPersonalizada as PermissaoPersonalizadaModel
else:  # pragma: no cover
    PermissaoPersonalizadaModel = object  # type: ignore[misc,assignment]
from shared.services.permission_resolver import PermissionResolver

pytestmark = pytest.mark.django_db


@pytest.fixture(name="tenant")
def fx_tenant() -> Tenant:
    """Cria tenant para testes de precedência envolvendo recurso."""
    return Tenant.objects.create(name="TPrecRes", subdomain="tprecres", enabled_modules={"modules": []})


@pytest.fixture(name="user_with_role")
def fx_user_with_role(tenant: Tenant) -> CustomUser:
    """Cria usuário com role ADMIN (para token is_admin em action map)."""
    user_model = get_user_model()
    user = cast("CustomUser", user_model.objects.create_user(username="u_prec_res_role", password="x"))  # noqa: S106
    role = Role.objects.create(tenant=tenant, name="ADMIN")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    return user


def _create_perm(
    user: CustomUser,
    tenant: Tenant,
    *,
    concedida: bool,
    recurso: str | None = None,
) -> PermissaoPersonalizadaModel:
    """Cria permissão personalizada auxiliar (retorna objeto do modelo)."""
    from user_management.models import PermissaoPersonalizada  # noqa: PLC0415

    return PermissaoPersonalizada.objects.create(
        user=user,
        modulo="produto",
        acao="VIEW",
        concedida=concedida,
        scope_tenant=tenant,
        recurso=recurso,
    )


@pytest.mark.usefixtures("tenant")
def test_precedencia_deny_global_vs_allow_resource(tenant: Tenant, user_with_role: CustomUser) -> None:
    """Deny global deve prevalecer sobre allow específico por recurso."""
    try:
        if importlib.util.find_spec("user_management.models") is None:  # pragma: no cover
            pytest.skip("Modelo PermissaoPersonalizada indisponível")
    except ImportError:  # pragma: no cover
        pytest.skip("Ambiente sem user_management (ImportError)")

    # deny global + allow recurso
    deny_global = _create_perm(user_with_role, tenant, concedida=False)
    allow_specific = _create_perm(user_with_role, tenant, concedida=True, recurso="ITEM:42")

    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_with_role.id, tenant_id=tenant.id)

    # Consultando recurso específico ainda deve negar pois deny global tem score base alto
    decision = resolver.explain_permission(
        user_with_role,
        tenant,
        "VIEW_PRODUTO",
        resource="ITEM:42",
        _force_trace=True,
    )
    assert decision.allowed is False  # noqa: S101
    assert decision.source == "personalizada"  # noqa: S101

    deny_global.delete()
    allow_specific.delete()


@pytest.mark.usefixtures("tenant")
def test_precedencia_allow_resource_sem_deny(tenant: Tenant, user_with_role: CustomUser) -> None:
    """Allow específico por recurso deve permitir quando não há deny global."""
    try:
        if importlib.util.find_spec("user_management.models") is None:  # pragma: no cover
            pytest.skip("Modelo PermissaoPersonalizada indisponível")
    except ImportError:  # pragma: no cover
        pytest.skip("Ambiente sem user_management (ImportError)")

    allow_specific = _create_perm(user_with_role, tenant, concedida=True, recurso="ITEM:99")
    resolver = PermissionResolver()
    resolver.invalidate_cache(user_id=user_with_role.id, tenant_id=tenant.id)
    decision = resolver.explain_permission(
        user_with_role,
        tenant,
        "VIEW_PRODUTO",
        resource="ITEM:99",
        _force_trace=True,
    )
    assert decision.allowed is True  # noqa: S101
    assert decision.source == "personalizada"  # noqa: S101
    allow_specific.delete()

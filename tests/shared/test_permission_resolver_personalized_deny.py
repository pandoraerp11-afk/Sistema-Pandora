"""Teste de precedence: personalized deny deve negar mesmo sem role.

Cenário: usuário sem role recebe uma permissão personalizada concedida=False
para ação mapeada; resolver deve retornar denied e trace conter 'personalizada'.
"""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib.auth import get_user_model

from core.models import CustomUser, Tenant, TenantUser
from shared.services.permission_resolver import PermissionResolver

pytestmark = pytest.mark.django_db


@pytest.fixture(name="tenant")
def fx_tenant() -> Tenant:
    """Cria tenant para o cenário de deny personalizada."""
    return Tenant.objects.create(name="TPermDeny", subdomain="tpdeny", enabled_modules={"modules": []})


@pytest.fixture(name="user_no_role")
def fx_user_no_role(tenant: Tenant) -> CustomUser:
    """Retorna usuário sem role para testar deny puro."""
    user_model = get_user_model()
    user = cast("CustomUser", user_model.objects.create_user(username="u_personal_deny", password="x"))  # noqa: S106
    TenantUser.objects.create(tenant=tenant, user=user)
    return user


def test_personalized_deny_without_role(tenant: Tenant, user_no_role: CustomUser) -> None:
    """Verifica que permissão personalizada com concedida=False nega acesso."""
    try:
        from user_management.models import PermissaoPersonalizada  # noqa: PLC0415
    except ImportError:
        pytest.skip("Modelo PermissaoPersonalizada indisponível")

    # Garantir que ação exista no action map via criação de role com permissão fictícia não usada
    # (o mapa é derivado de settings; se ação não existir cairá em default_result).
    # Inserimos permissão personalizada de deny.
    # O modelo usa campos modulo/acao separados, enquanto o resolver espera action combinada
    # Ex: action VIEW_PRODUTO -> modulo="PRODUTO" (ou "produto" case-insensitive) e acao="VIEW"
    perm = PermissaoPersonalizada.objects.create(
        user=user_no_role,
        modulo="produto",
        acao="VIEW",
        concedida=False,
        scope_tenant=tenant,
    )

    resolver = PermissionResolver()
    decision = resolver.explain_permission(user_no_role, tenant, "VIEW_PRODUTO", _force_trace=True)
    assert decision.allowed is False  # noqa: S101
    assert decision.source == "personalizada"  # noqa: S101 - garante origem
    # Cache path ainda retorna False
    assert resolver.has_permission(user_no_role, tenant, "VIEW_PRODUTO", _force_trace=True) is False  # noqa: S101

    perm.delete()

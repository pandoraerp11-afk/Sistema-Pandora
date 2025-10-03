"""Testes para debug_personalized do permission_resolver.

Casos cobertos:
* Ordenação (deny global antes de allow específico)
* Filtro de recurso não correspondente
* Permissão expirada marcada como não aplicada
"""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import CustomUser, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

pytestmark = pytest.mark.django_db

UserModel = get_user_model()


@pytest.fixture
def user() -> CustomUser:
    """Cria usuário simples para os cenários de permissão."""
    obj = UserModel.objects.create_user(username="u1", password="x", is_active=True)  # noqa: S106
    return cast("CustomUser", obj)


@pytest.fixture
def tenant() -> Tenant:
    """Cria um tenant de teste."""
    return Tenant.objects.create(name="T1", subdomain="t1")


@pytest.fixture
def tenant_user(user: CustomUser, tenant: Tenant) -> TenantUser:
    """Cria vínculo TenantUser garantindo contexto multi-tenant para futuras dependências."""
    return TenantUser.objects.create(user=user, tenant=tenant)


def test_debug_personalized_order_and_fields(
    user: CustomUser,
    tenant: Tenant,
    tenant_user: TenantUser,
) -> None:
    """Deny global deve vir antes do allow específico e campos essenciais devem existir."""
    PermissaoPersonalizada.objects.create(user=user, modulo="COTACAO", acao="VIEW", concedida=False)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="COTACAO",
        acao="VIEW",
        concedida=True,
        recurso="cotacao:55",
    )
    data = permission_resolver.debug_personalized(user, tenant, "VIEW_COTACAO", resource="cotacao:55")
    _ = tenant_user  # marca uso
    assert data  # noqa: S101
    assert data[0]["concedida"] is False  # noqa: S101
    assert any(item["recurso"] == "cotacao:55" for item in data)  # noqa: S101
    sample = data[0]
    for field in ("id", "concedida", "score", "aplicado", "motivo_exclusao"):
        assert field in sample  # noqa: S101


def test_debug_personalized_filters_non_matching_resource(
    user: CustomUser,
    tenant: Tenant,
) -> None:
    """Regra com recurso diferente não deve ser aplicada (aplicado False)."""
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="COTACAO",
        acao="VIEW",
        concedida=True,
        recurso="cotacao:99",
    )
    rows = permission_resolver.debug_personalized(user, tenant, "VIEW_COTACAO", resource="cotacao:55")
    assert rows  # noqa: S101
    assert any(r.get("aplicado") is False for r in rows)  # noqa: S101


def test_debug_personalized_expired(user: CustomUser, tenant: Tenant, tenant_user: TenantUser) -> None:
    """Permissão expirada deve aparecer com aplicado False."""
    past = timezone.now() - timezone.timedelta(days=1)
    PermissaoPersonalizada.objects.create(user=user, modulo="COTACAO", acao="VIEW", data_expiracao=past)
    rows = permission_resolver.debug_personalized(user, tenant, "VIEW_COTACAO")
    _ = tenant_user
    assert any(r.get("aplicado") is False for r in rows)  # noqa: S101

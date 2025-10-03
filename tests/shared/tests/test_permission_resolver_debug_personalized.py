"""Testes para debug_personalized do permission_resolver.

Foco: ordem (deny > allow), marcação de aplicado, filtros por recurso e expiração.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Tenant
from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user() -> Any:
    """Cria usuário simples para os cenários do permission resolver.

    Nota: o tipo concreto do modelo de usuário é dinâmico (get_user_model),
    por isso usamos Any para evitar falsos positivos de tipagem.
    """
    return User.objects.create_user(username="u1", password="x", is_active=True)  # noqa: S106


@pytest.fixture
def tenant() -> Tenant:
    """Cria um tenant simples padrão usado em todos os testes."""
    return Tenant.objects.create(name="T1", subdomain="t1")


@pytest.fixture
def tenant_user(user: Any, tenant: Tenant) -> Any:
    """Cria vínculo TenantUser garantindo que o usuário pertence ao tenant."""
    from core.models import TenantUser  # noqa: PLC0415

    return TenantUser.objects.create(user=user, tenant=tenant)


def test_debug_personalized_order_and_fields(user: Any, tenant: Tenant, tenant_user: Any) -> None:
    """Garante ordenação (deny primeiro) e presença dos campos básicos."""
    # Usa tenant_user apenas para evitar alerta de argumento não utilizado
    assert tenant_user is not None  # sanity
    PermissaoPersonalizada.objects.create(user=user, modulo="COTACAO", acao="VIEW", concedida=False)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="COTACAO",
        acao="VIEW",
        concedida=True,
        recurso="cotacao:55",
    )

    data = permission_resolver.debug_personalized(user, tenant, "VIEW_COTACAO", resource="cotacao:55")
    assert data, "Lista não deveria estar vazia"  # noqa: S101
    assert data[0]["concedida"] is False, "Deny global deve vir primeiro"  # noqa: S101
    assert any(item["recurso"] == "cotacao:55" for item in data)  # noqa: S101
    sample = data[0]
    for field in ("id", "concedida", "score", "aplicado", "motivo_exclusao"):
        assert field in sample  # noqa: S101


def test_debug_personalized_filters_non_matching_resource(user: Any, tenant: Tenant, tenant_user: Any) -> None:
    """Regra com recurso diferente não deve ser aplicada (aplicado False)."""
    assert tenant_user is not None
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


def test_debug_personalized_expired(user: Any, tenant: Tenant, tenant_user: Any) -> None:
    """Regra expirada aparece como não aplicada (score None / aplicado False)."""
    assert tenant_user is not None
    past = timezone.now() - timezone.timedelta(days=1)
    PermissaoPersonalizada.objects.create(user=user, modulo="COTACAO", acao="VIEW", data_expiracao=past)
    rows = permission_resolver.debug_personalized(user, tenant, "VIEW_COTACAO")
    assert any(r.get("aplicado") is False for r in rows)  # noqa: S101

"""Testes para a função `explain_permission` e a lógica de rastreamento."""

import sys
import types

import pytest
from django.conf import LazySettings
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import PermissionResult, explain_permission, permission_resolver

User = get_user_model()


@pytest.mark.django_db
def test_explain_permission_basic() -> None:
    """Verifica a explicação básica de uma permissão para um admin implícito."""
    user = User.objects.create(username="exu", is_active=True)
    tenant = Tenant.objects.create(name="TTX", slug="ttx")
    role = Role.objects.create(name="Admin", tenant=tenant)  # nome com Admin para is_admin implicit
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    result = explain_permission(user, tenant, "VIEW_FORNECEDOR")
    assert isinstance(result, PermissionResult)  # noqa: S101
    assert result.source == "role"  # noqa: S101
    assert result.allowed is True  # noqa: S101 # Admin deve ter permissão implícita


@pytest.mark.django_db
def test_explain_permission_cache_path() -> None:
    """Verifica se o caminho do cache é registrado corretamente na explicação."""
    user = User.objects.create(username="exu2", is_active=True)
    tenant = Tenant.objects.create(name="TTY", slug="tty")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Primeira chamada gera cache
    permission_resolver.has_permission(user, tenant, "UNKNOWN_ACTION")
    # Segunda deve vir do cache
    result = permission_resolver.explain_permission(user, tenant, "UNKNOWN_ACTION")
    assert result.source == "cache"  # noqa: S101


@pytest.mark.django_db
def test_action_map_merge_extra(django_settings: LazySettings) -> None:
    """Testa a capacidade de estender o mapa de ações via settings.PERMISSION_ACTION_MAP_EXTRA."""
    django_settings.PERMISSION_ACTION_MAP_EXTRA = {"VIEW_KIT_TESTE": ["can_view_kit_teste", "is_admin"]}
    user = User.objects.create(username="mergeu", is_active=True)
    tenant = Tenant.objects.create(name="TME", slug="tme")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    amap = permission_resolver._get_action_map(tenant)  # noqa: SLF001
    assert "VIEW_KIT_TESTE" in amap  # noqa: S101
    assert amap["VIEW_KIT_TESTE"] == ["can_view_kit_teste", "is_admin"]  # noqa: S101


@pytest.mark.django_db
def test_action_map_merge_provider(django_settings: LazySettings) -> None:
    """Testa a capacidade de estender o mapa de ações via um provedor dinâmico."""

    def provider() -> dict[str, list[str]]:
        return {"CREATE_WIDGET": ["can_create_widget", "is_admin"]}

    # Injetar provider via módulo dinâmico simples
    mod = types.ModuleType("dyn_provider_mod")
    mod.custom_provider = provider  # type: ignore[attr-defined]
    sys.modules["dyn_provider_mod"] = mod
    django_settings.PERMISSION_ACTION_MAP_PROVIDER = "dyn_provider_mod.custom_provider"

    user = User.objects.create(username="prov", is_active=True)
    tenant = Tenant.objects.create(name="TPR", slug="tpr")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    amap = permission_resolver._get_action_map(tenant)  # noqa: SLF001
    assert "CREATE_WIDGET" in amap  # noqa: S101
    assert amap["CREATE_WIDGET"][0] == "can_create_widget"  # noqa: S101

"""Testes básicos do permission_resolver (migrado).

Objetivo: validar caminhos fundamentais de cache, precedence e escopos
sem depender dos testes avançados.
"""

from __future__ import annotations

import os
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_role_allows() -> None:
    """Role 'admin' deve permitir VIEW_COTACAO (fluxo role->allow)."""
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm", subdomain="tperm")
    u = User.objects.create_user("permuser", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106 test pwd
    role = Role.objects.create(tenant=tenant, name="admin")
    # Marcador auxiliar (não usado pela lógica atual, mas mantido por compat):
    # Atributo auxiliar dinâmico usado somente em testes (não faz parte do modelo real).
    role.is_admin = True  # atributo dinâmico de teste
    role.save()
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_user_not_in_tenant() -> None:
    """Usuário sem vínculo TenantUser deve ser negado."""
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm2", subdomain="tperm2")
    u = User.objects.create_user("user2", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed is False
    assert "pertence" in reason.lower()


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_cache_behavior(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    """Segundo resolve deve resultar em cache hit estável (false->false)."""
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm3", subdomain="tperm3")
    uname = f"user_cache_{uuid.uuid4().hex[:6]}"
    u = User.objects.create_user(uname, password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106

    PermissaoPersonalizada.objects.filter(user=u).delete()
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    allowed1, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed1 is False
    allowed2, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed2 is False
    PermissaoPersonalizada.objects.create(user=u, modulo="cotacao", acao="view", concedida=True, scope_tenant=tenant)
    allowed_after_grant, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed_after_grant is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_resource_and_expiration() -> None:
    """Regras expiradas devem ser ignoradas e recurso específico negar corretamente."""
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm4", subdomain="tperm4")
    u = User.objects.create_user("user4", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    now = timezone.now()
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=True)
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=False,
        scope_tenant=tenant,
        recurso="lancamento:1",
    )
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=False,
        scope_tenant=tenant,
        recurso="lancamento:2",
        data_expiracao=now - timezone.timedelta(minutes=1),
    )
    allowed_r1, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="lancamento:1")
    allowed_r2, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="lancamento:2")
    assert allowed_r1 is False
    assert allowed_r2 is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_precedence_deny_over_allow() -> None:
    """Deny scoped deve prevalecer sobre allows mais genéricos e globais."""
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm5", subdomain="tperm5")
    u = User.objects.create_user("user5", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=True)
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=True,
        scope_tenant=tenant,
        recurso="doc:A",
    )
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=False,
        scope_tenant=tenant,
    )
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=False,
        scope_tenant=tenant,
        recurso="doc:B",
    )
    allowed_a, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:A")
    allowed_b, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:B")
    allowed_c, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:C")
    assert allowed_a is False
    assert allowed_b is False
    assert allowed_c is False

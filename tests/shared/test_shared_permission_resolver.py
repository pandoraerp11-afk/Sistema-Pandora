import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import permission_resolver

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_role_allows():
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm", subdomain="tperm")
    u = User.objects.create_user("permuser", password="x")
    role = Role.objects.create(tenant=tenant, name="admin")
    # Simular campo is_admin na role dinamicamente
    role.is_admin = True
    role.save()
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_user_not_in_tenant():
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm2", subdomain="tperm2")
    u = User.objects.create_user("user2", password="x")
    allowed, reason = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed is False and "pertence" in reason.lower()


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_cache_behavior(monkeypatch):
    cache.clear()
    tenant = Tenant.objects.create(name="Tperm3", subdomain="tperm3")
    import uuid

    uname = f"user_cache_{uuid.uuid4().hex[:6]}"
    u = User.objects.create_user(uname, password="x")
    from user_management.models import PermissaoPersonalizada

    PermissaoPersonalizada.objects.filter(user=u).delete()
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    # Primeira resolução (sem permissões) -> deve cachear False
    allowed1, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed1 is False
    # Segunda chamada sem mudanças deve vir do cache e continuar False
    allowed2, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed2 is False
    # Conceder permissão personalizada allow: design atual aplica imediatamente (invalidação reativa via signal)
    from user_management.models import PermissaoPersonalizada

    PermissaoPersonalizada.objects.create(user=u, modulo="cotacao", acao="view", concedida=True, scope_tenant=tenant)
    allowed_after_grant, _ = permission_resolver.resolve(u, tenant, "VIEW_COTACAO")
    assert allowed_after_grant is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_resource_and_expiration():
    from django.utils import timezone

    from user_management.models import PermissaoPersonalizada

    cache.clear()
    tenant = Tenant.objects.create(name="Tperm4", subdomain="tperm4")
    u = User.objects.create_user("user4", password="x")
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    now = timezone.now()
    # Global allow genérico
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=True)
    # Scoped deny mais específico com recurso e válido -> deve sobrepor
    PermissaoPersonalizada.objects.create(
        user=u, modulo="financeiro", acao="view", concedida=False, scope_tenant=tenant, recurso="lancamento:1"
    )
    # Expirada (não deve contar)
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="financeiro",
        acao="view",
        concedida=False,
        scope_tenant=tenant,
        recurso="lancamento:2",
        data_expiracao=now - timezone.timedelta(minutes=1),
    )
    # Test recurso 1 (deny)
    allowed_r1, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="lancamento:1")
    # Recurso 2 herda allow global (deny expirado ignorado)
    allowed_r2, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="lancamento:2")
    assert allowed_r1 is False
    assert allowed_r2 is True


@pytest.mark.django_db
@pytest.mark.permission
def test_permission_resolver_precedence_deny_over_allow():
    from user_management.models import PermissaoPersonalizada

    cache.clear()
    tenant = Tenant.objects.create(name="Tperm5", subdomain="tperm5")
    u = User.objects.create_user("user5", password="x")
    role = Role.objects.create(tenant=tenant, name="basic")
    TenantUser.objects.create(user=u, tenant=tenant, role=role)
    # Global allow genérico
    PermissaoPersonalizada.objects.create(user=u, modulo="financeiro", acao="view", concedida=True)
    # Scoped allow específico recurso A
    PermissaoPersonalizada.objects.create(
        user=u, modulo="financeiro", acao="view", concedida=True, scope_tenant=tenant, recurso="doc:A"
    )
    # Scoped deny genérico (deve ganhar de allows scoped/global)
    PermissaoPersonalizada.objects.create(
        user=u, modulo="financeiro", acao="view", concedida=False, scope_tenant=tenant
    )
    # Scoped deny recurso B (mais específico ainda para B)
    PermissaoPersonalizada.objects.create(
        user=u, modulo="financeiro", acao="view", concedida=False, scope_tenant=tenant, recurso="doc:B"
    )
    # Recurso A -> deny genérico scoped deve prevalecer sobre allow específico
    allowed_A, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:A")
    # Recurso B -> deny recurso específico
    allowed_B, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:B")
    # Recurso C (não listado) -> deny scoped genérico prevalece sobre allow global
    allowed_C, _ = permission_resolver.resolve(u, tenant, "VIEW_FINANCEIRO", resource="doc:C")
    assert allowed_A is False
    assert allowed_B is False
    assert allowed_C is False

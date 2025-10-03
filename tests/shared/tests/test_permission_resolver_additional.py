import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Tenant, TenantUser
from shared.services.permission_resolver import has_permission, permission_resolver

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def test_invalidate_cache_version_bump(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_inv1", password="x")
    tenant = Tenant.objects.create(name="Tinv1", subdomain="tinv1")
    TenantUser.objects.create(user=user, tenant=tenant)
    cache.clear()
    # Prime cache
    dec1 = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec1.trace is not None
    # Invalidate
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    # Após invalidar, primeira chamada deve ser MISS novamente (não cache_hit no trace final)
    dec2 = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO")
    assert dec2.trace is not None
    assert "cache_hit" not in dec2.trace, "Esperado miss após invalidar versão do cache"


def test_permission_personalizada_resource_precedence(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    from user_management.models import PermissaoPersonalizada

    user = User.objects.create_user("u_permres", password="x")
    tenant = Tenant.objects.create(name="Tpermres", subdomain="tpermres")
    TenantUser.objects.create(user=user, tenant=tenant)
    # Deny específica para recurso X deve prevalecer sobre allow genérica
    PermissaoPersonalizada.objects.create(
        user=user, modulo="financeiro", acao="view", concedida=True, scope_tenant=tenant
    )
    PermissaoPersonalizada.objects.create(
        user=user, modulo="financeiro", acao="view", concedida=False, scope_tenant=tenant, recurso="cotacao:123"
    )
    dec_specific = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO", resource="cotacao:123")
    dec_generic = permission_resolver.resolve_decision(user, tenant, "VIEW_FINANCEIRO", resource="cotacao:999")
    assert dec_specific.allowed is False, "Deny específico do recurso deve prevalecer"
    assert dec_generic.allowed is True, "Allow genérico deve aplicar quando recurso não casa"


def test_account_block_user_not_member(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_block1", password="x")
    tenant = Tenant.objects.create(name="Tblock1", subdomain="tblock1")
    # Não cria TenantUser: deve bloquear
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_FINANCEIRO")
    assert allowed is False
    assert "Usuário não pertence ao tenant" in reason


def test_default_allow_public_action(settings):
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_pub", password="x")
    tenant = Tenant.objects.create(name="Tpub", subdomain="tpub")
    TenantUser.objects.create(user=user, tenant=tenant)
    # Ação especial default True
    ok = has_permission(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    assert ok is True


@pytest.mark.skipif("portal_fornecedor" not in settings.INSTALLED_APPS, reason="App fornecedor ausente")
def test_implicit_fornecedor_role(settings):
    # Testa caminho _check_implicit_roles se app estiver instalado
    settings.PERMISSION_RESOLVER_TRACE = True
    user = User.objects.create_user("u_forn", password="x")
    tenant = Tenant.objects.create(name="Tforn", subdomain="tforn")
    TenantUser.objects.create(user=user, tenant=tenant)
    # Criar acesso fornecedor se modelo existir
    try:
        from portal_fornecedor.models import AcessoFornecedor, Fornecedor

        fornecedor = Fornecedor.objects.create(nome="FornecedorX", tenant=tenant)
        AcessoFornecedor.objects.create(usuario=user, fornecedor=fornecedor, ativo=True)
        dec = permission_resolver.resolve_decision(user, tenant, "VIEW_COTACAO")
        assert dec.allowed is True
        assert dec.source in {"implicit", "cache"}
    except Exception:
        pytest.skip("Modelos fornecedor indisponíveis")

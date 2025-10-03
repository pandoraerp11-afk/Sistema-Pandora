import pytest
from django.core.cache import cache

from shared.services.permission_resolver import PermissionResolver, permission_resolver


@pytest.mark.permission
def test_resolver_exception_path(monkeypatch, tenant_with_all_modules, auth_user, settings):
    """Força exceção em _check_account_blocks para validar caminho de erro e métrica."""
    settings.PERMISSION_RESOLVER_TRACE = True
    user, tenant, client = auth_user()
    called = {}

    def boom(*a, **kw):
        called["x"] = True
        raise RuntimeError("falha simulada")

    # Garante que não há cache prévio para essa combinação
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    monkeypatch.setattr(PermissionResolver, "_check_account_blocks", lambda self, u, t: boom())
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    assert not allowed
    assert "erro interno" in reason.lower()
    assert "exception:" in reason.lower()  # trace possui exception
    assert called.get("x") is True


@pytest.mark.permission
def test_cache_invalidation_version_bump(monkeypatch, tenant_with_all_modules, auth_user, settings):
    user, tenant, client = auth_user()
    # Aquecer cache
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    assert allowed is True or allowed is False  # apenas sanity
    # Capturar versão atual
    ver_key = f"{permission_resolver.cache_prefix}:ver:{user.id}:{tenant.id}"
    v1 = cache.get(ver_key)
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    v2 = cache.get(ver_key)
    assert v2 == v1 + 1
    # Chave antiga não deve ser usada (nova resolução deve gerar cache com nova versão)
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    # Sanity: deve retornar tupla coerente e reason não vazio
    assert isinstance(allowed2, bool)
    assert isinstance(reason2, str) and reason2


@pytest.mark.permission
def test_metrics_counters_increment(monkeypatch, tenant_with_all_modules, auth_user, settings):
    """Se prometheus estiver instalado, counters devem aumentar em fluxo cold + warm."""
    if not permission_resolver._m_decisions:
        pytest.skip("Métricas desabilitadas (prometheus ausente)")
    settings.PERMISSION_RESOLVER_TRACE = False
    user, tenant, client = auth_user()
    action = "VIEW_DASHBOARD_PUBLIC"
    # Garantir chave limpa
    cache.clear()
    before_cache_hits = permission_resolver._m_cache_hits._value.get()  # type: ignore
    permission_resolver.resolve(user, tenant, action)
    permission_resolver.resolve(user, tenant, action)  # warm
    after_cache_hits = permission_resolver._m_cache_hits._value.get()  # type: ignore
    assert after_cache_hits == before_cache_hits + 1

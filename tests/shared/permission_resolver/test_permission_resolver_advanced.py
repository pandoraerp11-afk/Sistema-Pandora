"""Migrado de shared/tests/test_permission_resolver_advanced.py."""

from __future__ import annotations

# ruff: noqa: ANN001, D103
import pytest
from django.core.cache import cache

from shared.services.permission_resolver import PermissionResolver, permission_resolver


@pytest.mark.permission
def test_resolver_exception_path(monkeypatch: pytest.MonkeyPatch, tenant_with_all_modules, auth_user, settings) -> None:
    settings.PERMISSION_RESOLVER_TRACE = True
    user, tenant, client = auth_user()
    called = {}

    def boom() -> None:
        called["x"] = True
        msg = "falha simulada"
        raise RuntimeError(msg)

    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    monkeypatch.setattr(PermissionResolver, "_check_account_blocks", lambda *a, **k: boom())  # noqa: ARG005
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    assert not allowed
    assert "erro interno" in reason.lower()
    assert "exception:" in reason.lower()
    assert called.get("x") is True


@pytest.mark.permission
def test_cache_invalidation_version_bump(
    monkeypatch: pytest.MonkeyPatch,  # noqa: ARG001
    tenant_with_all_modules,
    auth_user,
    settings,
) -> None:
    user, tenant, client = auth_user()
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    assert allowed is True or allowed is False
    ver_key = f"{permission_resolver.cache_prefix}:ver:{user.id}:{tenant.id}"
    v1 = cache.get(ver_key)
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    v2 = cache.get(ver_key)
    assert v2 == v1 + 1
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    assert isinstance(allowed2, bool)
    assert isinstance(reason2, str)
    assert reason2 != ""


@pytest.mark.permission
def test_placeholder_metrics_skip() -> None:
    """Placeholder: métricas desativadas; manter para futura reintrodução."""
    assert True

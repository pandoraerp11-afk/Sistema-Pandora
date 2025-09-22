import json

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "strict_flag,expect_403_reason",
    [
        (True, "PERMISSION_RESOLVER_DENY"),
        (False, "OK"),  # sem strict: negação do resolver não bloqueia (desde que módulo habilitado)
    ],
)
def test_permission_resolver_strict_behavior(settings, client, monkeypatch, strict_flag, expect_403_reason):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = strict_flag
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="T1", slug="t1", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("user_strict", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, *a, **k):
            return False, "DENY_TEST"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    resp = client.get("/clientes/")
    if strict_flag:
        assert resp.status_code == 403
        assert resp.headers.get("X-Deny-Reason") == expect_403_reason
        assert AuditLog.objects.filter(change_message__contains="[MODULE_DENY]").count() == 1
    else:
        # Sem strict deve permitir (status != 403)
        assert resp.status_code != 403
        assert resp.headers.get("X-Deny-Reason") is None
        assert AuditLog.objects.filter(change_message__contains="[MODULE_DENY]").count() == 0


@pytest.mark.django_db
def test_portal_user_whitelist_bypass_resolver(settings, client, monkeypatch):
    """Usuário portal em whitelist deve acessar mesmo se resolver nega quando módulo está habilitado."""
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True  # strict liga em geral
    settings.FEATURE_MODULE_DENY_403 = True
    settings.PORTAL_ALLOWED_MODULES = ["clientes"]

    from core.models import Tenant

    tenant = Tenant.objects.create(nome="TP", slug="tp", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("portal1", password="x", user_type="PORTAL")
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, *a, **k):
            return False, "DENY_TEST"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    resp = client.get("/clientes/")
    # Deve permitir (não 403) porque whitelist bypassa resolver
    assert resp.status_code != 403
    assert resp.headers.get("X-Deny-Reason") is None


@pytest.mark.django_db
def test_non_403_flow_sets_headers_when_disabled_403_flag(settings, client, monkeypatch):
    """Quando FEATURE_MODULE_DENY_403=False deve redirecionar (200/302 final) mas ainda registrar log e NÃO incluir X-Deny-Reason no redirect final.
    Em ambiente de teste podemos inspecionar log e mensagens."""
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_MODULE_DENY_403 = False  # modo redirect
    settings.FEATURE_LOG_MODULE_DENIALS = True
    settings.TESTING = True  # para headers de debug no redirect legado

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="T2", slug="t2", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("user_redirect", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, *a, **k):
            return False, "DENY_TEST"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    resp = client.get("/clientes/", follow=True)
    # Não deve ser 403; fluxo redirect termina em 200
    assert resp.status_code in {200, 302}
    assert resp.redirect_chain  # houve redirect
    # Log foi criado
    assert AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]").count() == 1


@pytest.mark.django_db
def test_module_deny_metric_counter(settings, client, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True
    settings.LOG_MODULE_DENY_DEDUP_SECONDS = 0  # sem dedup para contar múltiplas

    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="T3", slug="t3", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("user_metric", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, *a, **k):
            return False, "DENY_TEST"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    from django.core.cache import cache

    key = "module_deny_count:clientes:PERMISSION_RESOLVER_DENY"
    assert cache.get(key) in {None, 0}
    client.get("/clientes/")
    v1 = cache.get(key)
    assert v1 == 1
    client.get("/clientes/")
    v2 = cache.get(key)
    # Sem dedup deve incrementar novamente
    assert v2 == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enabled_modules_field,expected",
    [
        (json.dumps(["clientes", "obras"]), True),  # string JSON list
        (["clientes", "obras"], True),  # lista direta
        ({"modules": ["obras"]}, False),  # dict com modules sem 'clientes'
    ],
)
def test_tenant_has_module_variations(settings, enabled_modules_field, expected, client):
    settings.FEATURE_UNIFIED_ACCESS = True

    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TX", slug="tx", enabled_modules=enabled_modules_field)
    user = User.objects.create_user("user_tx", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    resp = client.get("/clientes/")
    if expected:
        assert resp.status_code != 403  # acesso permitido
    # pode ser 403 (strict deny) ou redirect dependendo de flags; checar que não 200 direto se negado
    elif resp.status_code == 403:
        assert resp.headers.get("X-Deny-Reason") in {"MODULE_DISABLED_FOR_TENANT", "PERMISSION_RESOLVER_DENY"}
    else:
        # permitido erroneamente seria falha; permitir apenas se resolver liberal (não configurado aqui)
        assert resp.status_code in {302, 200}

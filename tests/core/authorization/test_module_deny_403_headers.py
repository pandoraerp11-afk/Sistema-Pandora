import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_resolver_deny_sets_headers_403(settings, client, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True
    settings.LOG_MODULE_DENY_DEDUP_SECONDS = 5

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="H1", slug="h1", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("huser", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    # Resolver nega explicitamente
    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, *a, **k):
            return False, "DENY_TEST"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    resp = client.get("/clientes/")
    assert resp.status_code == 403
    assert resp.headers.get("X-Deny-Reason") in {"PERMISSION_RESOLVER_DENY", "MODULE_DISABLED_FOR_TENANT"}
    assert resp.headers.get("X-Deny-Module") == "clientes"
    # Log criado
    assert (
        AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]", change_message__contains="clientes").count()
        == 1
    )


@pytest.mark.django_db
def test_dedup_logging(settings, client, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True
    settings.LOG_MODULE_DENY_DEDUP_SECONDS = 60

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="H2", slug="h2", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("huser2", password="x")
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

    # Primeira requisição
    resp1 = client.get("/clientes/")
    assert resp1.status_code == 403
    # Segunda requisição (mesmo usuário/módulo/motivo) não deve criar log novo
    resp2 = client.get("/clientes/")
    assert resp2.status_code == 403
    logs = AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]", change_message__contains="clientes")
    assert logs.count() == 1

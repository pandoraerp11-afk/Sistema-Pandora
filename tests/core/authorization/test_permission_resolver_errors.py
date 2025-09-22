import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("strict_flag", [True, False])
def test_resolver_internal_error_strict_vs_permissive(settings, client, monkeypatch, strict_flag):
    """Simula erro interno no permission_resolver.resolve e verifica efeito no middleware can_access_module.
    Estrutura: monkeypatch resolver para raise Exception. Strict=True deve gerar 403 com REASON_UNKNOWN_ERROR.
    Strict=False deve permitir acesso (não 403)."""
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = strict_flag
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TE", slug="te", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("user_err", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    from shared.services import permission_resolver as pr_mod

    class Boom:
        def resolve(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(pr_mod, "permission_resolver", Boom())

    resp = client.get("/clientes/")
    if strict_flag:
        assert resp.status_code == 403
        assert resp.headers.get("X-Deny-Reason") in {
            "UNKNOWN_ERROR",
            "PERMISSION_RESOLVER_DENY",
            "REASON_UNKNOWN_ERROR",
        }
        assert AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]").count() == 1
    else:
        assert resp.status_code != 403
        assert AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]").count() == 0

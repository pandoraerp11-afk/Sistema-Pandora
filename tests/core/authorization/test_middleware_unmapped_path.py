import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_unmapped_path_no_module_log(settings, client):
    """Acesso a path não mapeado em MODULE_URL_MAPPING não deve gerar log [MODULE_DENY]."""
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_MODULE_DENY_403 = True
    settings.FEATURE_LOG_MODULE_DENIALS = True

    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TU", slug="tu", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("user_unmapped", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    resp = client.get("/algum_path_que_nao_existe_modulo/")
    # Não deve ser 403 pois não há módulo verificado (pode 404 dependendo roteamento)
    assert resp.status_code in {200, 302, 301, 404}
    assert AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]").count() == 0

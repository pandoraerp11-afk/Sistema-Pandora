import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


@pytest.mark.django_db
def test_menu_excludes_module_on_resolver_strict_denial(settings, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TA", slug="ta", enabled_modules={"modules": ["clientes", "financeiro"]})
    user = User.objects.create_user("u_strict", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)

    # Monkeypatch resolver para negar VIEW_CLIENTES
    from shared.services import permission_resolver as pr_mod

    class DenyClientesResolver:
        def resolve(self, user, tenant, action_code):
            if action_code == "VIEW_CLIENTES":
                return False, "DENY_TEST"
            return True, "ALLOW"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyClientesResolver())

    # Render menu
    from django.template import Context, Template

    tpl = Template("{% load menu_tags %}{% render_sidebar_menu %}")

    # Fake request com sessão
    class R:
        pass

    r = R()
    r.user = user
    r.session = {"tenant_id": tenant.id}
    r.path = "/"
    out = tpl.render(Context({"request": r}))
    assert "financeiro" in out.lower()
    assert "clientes" not in out.lower()


@pytest.mark.django_db
def test_middleware_logs_resolver_denial(settings, client, monkeypatch):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = True
    settings.FEATURE_LOG_MODULE_DENIALS = True
    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TB", slug="tb", enabled_modules={"modules": ["clientes"]})
    user = User.objects.create_user("u_log", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)
    # Colocar tenant na sessão
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    # Resolver nega VIEW_CLIENTES
    from shared.services import permission_resolver as pr_mod

    class DenyAll:
        def resolve(self, user, tenant, action_code):
            return False, "FORCED_DENY"

    monkeypatch.setattr(pr_mod, "permission_resolver", DenyAll())

    resp = client.get("/clientes/")
    assert resp.status_code in (302, 403)
    assert (
        AuditLog.objects.filter(change_message__startswith="[MODULE_DENY]", change_message__contains="clientes").count()
        == 1
    )


@pytest.mark.django_db
def test_middleware_logs_portal_whitelist_denial(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos"]  # clientes fora
    from core.models import AuditLog, Tenant, TenantUser

    tenant = Tenant.objects.create(nome="TC", slug="tc", enabled_modules={"modules": ["clientes", "documentos"]})
    user = User.objects.create_user("u_portal", password="x")
    user.user_type = "PORTAL"
    grp, _ = Group.objects.get_or_create(name=getattr(settings, "PORTAL_USER_GROUP_NAME", "PortalUser"))
    user.groups.add(grp)
    user.save()
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=False)
    client.force_login(user)
    s = client.session
    s["tenant_id"] = tenant.id
    s.save()

    resp = client.get("/clientes/")
    assert resp.status_code in (302, 403)
    assert AuditLog.objects.filter(
        change_message__startswith="[MODULE_DENY]", change_message__contains="clientes"
    ).exists()
    # Acesso permitido para whitelisted
    client.get("/documentos/") if hasattr(tenant, "id") else None
    # Não forçamos assert de sucesso (rota pode exigir view), apenas garantir que não logou deny adicional para documentos
    deny_docs = AuditLog.objects.filter(
        change_message__startswith="[MODULE_DENY]", change_message__contains="documentos"
    ).count()
    assert deny_docs == 0

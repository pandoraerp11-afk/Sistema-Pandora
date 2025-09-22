import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template

User = get_user_model()

MENU_TEMPLATE = """{% load menu_tags %}{% render_sidebar_menu %}"""


@pytest.mark.django_db
def test_portal_menu_whitelist(settings, client):
    settings.FEATURE_UNIFIED_ACCESS = True
    settings.PORTAL_ALLOWED_MODULES = ["documentos", "notifications"]
    user = User.objects.create_user("portal_menu", password="x")
    user.user_type = "PORTAL"
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(
        nome="Tmenu", slug="tmenu", enabled_modules='["documentos","clientes","notifications"]'
    )
    # Criar vínculo TenantUser para fallback de get_current_tenant
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    client.force_login(user)

    # Requisitar uma view simples para garantir sessão carregada e setar tenant_id
    session = client.session
    session["tenant_id"] = tenant.id
    session.save()

    class DummyReq:
        def __init__(self, user, session):
            self.user = user
            self.session = session
            self.path = "/"

    req = DummyReq(user, session)
    out = Template(MENU_TEMPLATE).render(Context({"request": req}))
    assert "documentos" in out
    assert "notifications" in out
    assert "clientes" not in out

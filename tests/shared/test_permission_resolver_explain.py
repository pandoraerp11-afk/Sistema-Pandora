import pytest
from django.contrib.auth import get_user_model

from shared.services.permission_resolver import explain_permission, permission_resolver

User = get_user_model()


@pytest.mark.django_db
def test_explain_permission_basic(settings):
    from core.models import Role, Tenant, TenantUser

    user = User.objects.create(username="exu", is_active=True)
    tenant = Tenant.objects.create(name="TTX", slug="ttx")
    role = Role.objects.create(name="Admin", tenant=tenant)  # nome com Admin para is_admin implicit
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    info = explain_permission(user, tenant, "VIEW_FORNECEDOR")
    assert info["action"] == "VIEW_FORNECEDOR"
    assert "action_tokens" in info and isinstance(info["action_tokens"], list)
    assert "steps" in info and isinstance(info["steps"], list)
    # Deve ter source role ou default dependendo dos tokens
    assert info["source"] in {"role", "default", "implicit", "cache"}


@pytest.mark.django_db
def test_explain_permission_cache_path(settings):
    from core.models import Role, Tenant, TenantUser

    user = User.objects.create(username="exu2", is_active=True)
    tenant = Tenant.objects.create(name="TTY", slug="tty")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Primeira chamada gera cache
    explain_permission(user, tenant, "UNKNOWN_ACTION")
    # Segunda deve mostrar cache_hit como primeiro passo
    info2 = explain_permission(user, tenant, "UNKNOWN_ACTION")
    steps = info2.get("steps", [])
    assert steps and steps[0].startswith("cache_hit")


@pytest.mark.django_db
def test_action_map_merge_extra(settings):
    from core.models import Role, Tenant, TenantUser

    settings.PERMISSION_ACTION_MAP_EXTRA = {"VIEW_KIT_TESTE": ["can_view_kit_teste", "is_admin"]}
    user = User.objects.create(username="mergeu", is_active=True)
    tenant = Tenant.objects.create(name="TME", slug="tme")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    amap = permission_resolver._get_action_map()
    assert "VIEW_KIT_TESTE" in amap
    assert amap["VIEW_KIT_TESTE"] == ["can_view_kit_teste", "is_admin"]


@pytest.mark.django_db
def test_action_map_merge_provider(settings, monkeypatch):
    from core.models import Role, Tenant, TenantUser

    def provider():
        return {"CREATE_WIDGET": ["can_create_widget", "is_admin"]}

    # Injetar provider via módulo dinâmico simples
    # Criar módulo fake em runtime
    import sys
    import types

    mod = types.ModuleType("dyn_provider_mod")
    mod.custom_provider = provider
    sys.modules["dyn_provider_mod"] = mod
    settings.PERMISSION_ACTION_MAP_PROVIDER = "dyn_provider_mod.custom_provider"

    user = User.objects.create(username="prov", is_active=True)
    tenant = Tenant.objects.create(name="TPR", slug="tpr")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    amap = permission_resolver._get_action_map()
    assert "CREATE_WIDGET" in amap
    assert amap["CREATE_WIDGET"][0] == "can_create_widget"

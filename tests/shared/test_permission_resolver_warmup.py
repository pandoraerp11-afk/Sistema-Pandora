import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_permission_resolver_warmup_on_login(client, settings):
    """Verifica que o login dispara aquecimento e o segundo resolve é cache-hit com trace."""
    settings.PERMISSION_RESOLVER_TRACE = True
    settings.PERMISSION_WARMUP_ON_LOGIN = True
    # reduzir ações de warmup para controle
    settings.PERMISSION_WARMUP_ACTIONS = ["VIEW_DASHBOARD_PUBLIC"]

    from core.models import Role, Tenant, TenantUser
    from shared.services.permission_resolver import permission_resolver

    # cria user e tenant com role básica
    user = User.objects.create_user(username="warm", password="x", is_active=True)
    tenant = Tenant.objects.create(name="T", slug="t")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # login via client já configura tenant_id via conftest e dispara signal
    assert client.login(username="warm", password="x")

    # primeira consulta deve já vir de cache (warmup) e conter cache_hit no trace
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_DASHBOARD_PUBLIC")
    assert allowed is True or allowed is False
    assert "cache_hit" in reason

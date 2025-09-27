"""Testes de idempotência para atribuição de role default em TenantUser."""

import pytest
from django.contrib.auth import get_user_model

from core.models import ROLE_DEFAULT_NAME, Role, Tenant, TenantUser

pytestmark = pytest.mark.django_db


def test_tenantuser_default_role_idempotent() -> None:
    """Garante que a primeira criação atribui role default e não duplica papel."""
    tenant = Tenant.objects.create(name="Empresa Z", subdomain="empresa-z", enabled_modules={"modules": []})
    user_model = get_user_model()
    # Senha curta e hardcoded aceitável em contexto de teste isolado.
    user = user_model.objects.create_user(username="user_idemp", password="x")  # noqa: S106 (test password)

    tu1 = TenantUser.objects.create(tenant=tenant, user=user)
    # Uso de assert do pytest é intencional aqui.
    assert tu1.role is not None  # noqa: S101
    assert tu1.role.name == ROLE_DEFAULT_NAME  # noqa: S101

    count_roles = Role.objects.filter(tenant=tenant, name=ROLE_DEFAULT_NAME).count()
    assert count_roles == 1  # noqa: S101

    tu1.refresh_from_db()
    assert tu1.role.name == ROLE_DEFAULT_NAME  # noqa: S101

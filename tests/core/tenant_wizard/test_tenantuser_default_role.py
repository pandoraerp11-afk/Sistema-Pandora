import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_tenantuser_auto_role_default_created():
    tenant = Tenant.objects.create(name="Empresa Y", slug="empresa-y", enabled_modules={"modules": []})
    user = User.objects.create_user(username="user_default_role", password="x")
    tu = TenantUser.objects.create(tenant=tenant, user=user)  # sem role explícita
    tu.refresh_from_db()
    assert tu.role is not None, "Role default não atribuída"
    assert tu.role.name == "USER"
    # Garantir idempotência: criar outra associação não duplica role
    role_count_before = Role.objects.filter(tenant=tenant, name="USER").count()
    # Forçar novo save sem alterar role
    tu.save()
    role_count_after = Role.objects.filter(tenant=tenant, name="USER").count()
    assert role_count_before == role_count_after, "Save subsequente não deve criar nova role USER"

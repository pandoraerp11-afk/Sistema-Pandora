"""Migrado de shared/tests/test_ui_permissions_module_key.py."""

import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant, TenantUser
from shared.services.ui_permissions import build_ui_permissions

User = get_user_model()


@pytest.mark.django_db
def test_ui_perms_fornecedor_superuser():
    user = User.objects.create(username="su", is_superuser=True)
    tenant = Tenant.objects.create(name="T1", schema_name="t1")
    perms = build_ui_permissions(user, tenant, module_key="FORNECEDOR")
    assert all(perms.values())


@pytest.mark.django_db
def test_ui_perms_fornecedor_tenant_admin():
    user = User.objects.create(username="adm")
    tenant = Tenant.objects.create(name="T2", schema_name="t2")
    role = Role.objects.create(tenant=tenant, name="USER")
    TenantUser.objects.create(user=user, tenant=tenant, role=role, is_tenant_admin=True)
    perms = build_ui_permissions(user, tenant, module_key="FORNECEDOR")
    assert all(perms.values())


@pytest.mark.django_db
def test_ui_perms_fornecedor_regular_role():
    user = User.objects.create(username="usr")
    tenant = Tenant.objects.create(name="T3", schema_name="t3")
    role = Role.objects.create(tenant=tenant, name="BASIC")
    TenantUser.objects.create(user=user, tenant=tenant, role=role)
    perms = build_ui_permissions(user, tenant, module_key="FORNECEDOR")
    assert perms == {"can_view": False, "can_add": False, "can_edit": False, "can_delete": False}


@pytest.mark.django_db
def test_ui_perms_funcionario_superuser():
    user = User.objects.create(username="su2", is_superuser=True)
    tenant = Tenant.objects.create(name="T4", schema_name="t4")
    perms = build_ui_permissions(user, tenant, module_key="FUNCIONARIO")
    assert all(perms.values())

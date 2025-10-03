"""Migrado de shared/tests/test_permission_resolver_expiration_resource.py."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Role, Tenant, TenantUser
from shared.services.permission_resolver import has_permission
from user_management.models import PermissaoPersonalizada

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.permission
def test_expired_and_future_permissions():
    tenant = Tenant.objects.create(name="Empresa Y", subdomain="emp-y")
    user = User.objects.create_user(username="u2", password="pass", email="u2@example.com")
    role = Role.objects.create(tenant=tenant, name="RoleY")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="docs",
        acao="view",
        concedida=True,
        data_expiracao=timezone.now() - timedelta(days=1),
        scope_tenant=tenant,
    )
    assert has_permission(user, tenant, "view_docs") is False
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="docs",
        acao="view",
        concedida=True,
        data_expiracao=timezone.now() + timedelta(days=1),
        scope_tenant=tenant,
    )
    assert has_permission(user, tenant, "view_docs") is True


@pytest.mark.django_db
@pytest.mark.permission
def test_resource_specific_and_wildcard():
    tenant = Tenant.objects.create(name="Empresa Z", subdomain="emp-z")
    user = User.objects.create_user(username="u3", password="pass", email="u3@example.com")
    role = Role.objects.create(tenant=tenant, name="RoleZ")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="files",
        acao="download",
        recurso="arquivo-123",
        concedida=True,
        scope_tenant=tenant,
    )
    assert has_permission(user, tenant, "download_files") is False
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="files",
        acao="download",
        concedida=True,
        scope_tenant=tenant,
    )
    assert has_permission(user, tenant, "download_files", "arquivo-xyz") is True


@pytest.mark.django_db
@pytest.mark.permission
def test_resource_deny_overrides_wildcard():
    tenant = Tenant.objects.create(name="Empresa W", subdomain="emp-w")
    user = User.objects.create_user(username="u4", password="pass", email="u4@example.com")
    role = Role.objects.create(tenant=tenant, name="RoleW")
    TenantUser.objects.create(tenant=tenant, user=user, role=role)
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="files",
        acao="download",
        concedida=True,
        scope_tenant=tenant,
    )
    PermissaoPersonalizada.objects.create(
        user=user,
        modulo="files",
        acao="download",
        recurso="arquivo-xyz",
        concedida=False,
        scope_tenant=tenant,
    )
    assert has_permission(user, tenant, "download_files", "arquivo-xyz") is False

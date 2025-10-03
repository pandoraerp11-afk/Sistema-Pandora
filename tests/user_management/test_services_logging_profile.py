"""Migrado de user_management/tests/test_services_logging_profile.py."""

import os

import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant
from user_management.models import LogAtividadeUsuario, StatusUsuario
from user_management.services import logging_service, profile_service

User = get_user_model()
pytestmark = [pytest.mark.django_db]


def test_log_activity_creates_entry() -> None:
    """Cria registro padrão com IP/UA de fallback quando omitidos."""
    u = User.objects.create_user("logger", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106
    logging_service.log_activity(u, "LOGIN", "AUTH", "Login efetuado", ip=None, user_agent=None)
    rec = LogAtividadeUsuario.objects.get(user=u)
    assert rec.acao == "LOGIN"
    # IP de fallback definido pelo serviço para ausências (aceito em GenericIPAddressField)
    assert rec.ip_address == "0.0.0.0"  # noqa: S104
    assert rec.user_agent == "N/A"


def test_log_activity_silent_on_no_user() -> None:
    """Nenhuma entrada deve ser criada quando user é None."""
    logging_service.log_activity(None, "X", "M", "Desc")
    assert LogAtividadeUsuario.objects.count() == 0


def test_ensure_profile_and_sync_status() -> None:
    """Sincroniza status entre usuário ativo/inativo e perfil."""
    u = User.objects.create_user("prof", password=os.getenv("TEST_PASSWORD", "x"), is_active=True)  # nosec S106
    p1 = profile_service.ensure_profile(u)
    assert p1.status in (StatusUsuario.ATIVO, StatusUsuario.PENDENTE, StatusUsuario.INATIVO)
    p1.status = StatusUsuario.INATIVO
    p1.save(update_fields=["status"])
    u.refresh_from_db()
    if not u.is_active:
        u.is_active = True
        u.save(update_fields=["is_active"])
    profile_service.sync_status(u)
    p1.refresh_from_db()
    assert p1.status == StatusUsuario.ATIVO
    u.is_active = False
    u.save(update_fields=["is_active"])
    profile_service.sync_status(u)
    p1.refresh_from_db()
    assert p1.status == StatusUsuario.INATIVO


def test_ensure_tenant_membership_with_default_role() -> None:
    """Cria vínculo tenant+role padrão apenas uma vez."""
    u = User.objects.create_user("memb", password=os.getenv("TEST_PASSWORD", "x"))  # nosec S106
    tenant = Tenant.objects.create(name="T", subdomain="t-serv")

    def factory(t: Tenant) -> Role:
        return Role.objects.create(tenant=t, name="BASIC")

    tu = profile_service.ensure_tenant_membership(u, tenant, default_role_factory=factory)
    assert tu.role is not None
    assert tu.role.name == "BASIC"
    tu2 = profile_service.ensure_tenant_membership(u, tenant, default_role_factory=factory)
    assert tu2.id == tu.id

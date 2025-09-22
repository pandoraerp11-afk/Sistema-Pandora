import pytest
from django.contrib.auth import get_user_model

from core.models import Role, Tenant
from user_management.models import LogAtividadeUsuario, StatusUsuario
from user_management.services import logging_service, profile_service

User = get_user_model()
pytestmark = [pytest.mark.django_db]


def test_log_activity_creates_entry():
    u = User.objects.create_user("logger", password="x")
    logging_service.log_activity(u, "LOGIN", "AUTH", "Login efetuado", ip=None, user_agent=None)
    rec = LogAtividadeUsuario.objects.get(user=u)
    assert rec.acao == "LOGIN"
    assert rec.ip_address == "0.0.0.0"
    assert rec.user_agent == "N/A"


def test_log_activity_silent_on_no_user():
    # Não deve criar nada
    logging_service.log_activity(None, "X", "M", "Desc")  # type: ignore
    assert LogAtividadeUsuario.objects.count() == 0


def test_ensure_profile_and_sync_status():
    u = User.objects.create_user("prof", password="x", is_active=True)
    p1 = profile_service.ensure_profile(u)
    assert p1.status in (StatusUsuario.ATIVO, StatusUsuario.PENDENTE, StatusUsuario.INATIVO)
    # Força INATIVO e user ativo -> sync promove
    p1.status = StatusUsuario.INATIVO
    p1.save(update_fields=["status"])
    # O sinal post_save do perfil define user.is_active=False quando perfil fica INATIVO.
    # Reativamos explicitamente para simular fluxo onde usuário continua ativo e validar promoção.
    u.refresh_from_db()
    if not u.is_active:
        u.is_active = True
        u.save(update_fields=["is_active"])
    profile_service.sync_status(u)
    p1.refresh_from_db()
    assert p1.status == StatusUsuario.ATIVO
    # Desativa user => perfil vai para INATIVO
    u.is_active = False
    u.save(update_fields=["is_active"])
    profile_service.sync_status(u)
    p1.refresh_from_db()
    assert p1.status == StatusUsuario.INATIVO


def test_ensure_tenant_membership_with_default_role():
    u = User.objects.create_user("memb", password="x")
    tenant = Tenant.objects.create(name="T", subdomain="t-serv")

    def factory(t):
        return Role.objects.create(tenant=t, name="BASIC")

    tu = profile_service.ensure_tenant_membership(u, tenant, default_role_factory=factory)
    assert tu.role and tu.role.name == "BASIC"
    # Idempotente
    tu2 = profile_service.ensure_tenant_membership(u, tenant, default_role_factory=factory)
    assert tu2.id == tu.id

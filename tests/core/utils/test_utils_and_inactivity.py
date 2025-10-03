"""Testes utilitários e de inatividade.

Foca em:
* get_current_tenant (seleção automática / limpeza de sessão)
* SessionInactivityMiddleware (expiração e refresh)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest  # noqa: TC002 - import runtime deliberado para clareza nos testes
from django.test import RequestFactory
from django.utils import timezone

if TYPE_CHECKING:  # imports só para tipagem leve
    from django.conf import LazySettings
    from django.contrib.auth.models import AbstractBaseUser
    from django.test.client import Client

from core.middleware_session_inactivity import SessionInactivityMiddleware
from core.models import Tenant, TenantUser
from core.utils import get_current_tenant
from user_management.models import SessaoUsuario

User = get_user_model()
pytestmark = [pytest.mark.django_db]


def _make_request(user: object | None = None) -> HttpRequest:
    rf = RequestFactory()
    req = rf.get("/")
    if user:
        req.user = user
    else:

        class DummyAnon:
            is_authenticated = False

        req.user = DummyAnon()
    # simulate session dict
    req.session = {}
    return req


def test_get_current_tenant_none_without_session() -> None:
    """Sem tenant_id e sem memberships retorna None."""
    req = _make_request()
    t = get_current_tenant(req)
    assert t is None


def test_get_current_tenant_auto_select_single_membership() -> None:
    """Seleciona automaticamente único tenant de membership, cacheando resultado."""
    pwd = os.environ.get("TEST_PASSWORD", "x")
    user = User.objects.create_user("u_auto", password=pwd)
    tenant = Tenant.objects.create(name="Tauto", subdomain="tauto")
    TenantUser.objects.create(user=user, tenant=tenant)
    req = _make_request(user)
    t = get_current_tenant(req)
    assert t == tenant
    assert hasattr(req, "_cached_tenant")
    t2 = get_current_tenant(req)
    assert t2 is t


def test_get_current_tenant_invalid_id_clears_session() -> None:
    """ID inválido remove chave tenant_id da sessão e retorna None."""
    pwd = os.environ.get("TEST_PASSWORD", "x")
    user = User.objects.create_user("u_bad", password=pwd)
    tenant = Tenant.objects.create(name="Tbad", subdomain="tbad")
    TenantUser.objects.create(user=user, tenant=tenant)
    req = _make_request(user)
    req.session["tenant_id"] = 999999
    t = get_current_tenant(req)
    assert t is None
    assert "tenant_id" not in req.session


def test_get_current_tenant_inactive_status() -> None:
    """Tenant inativo não é retornado mesmo se tenant_id presente."""
    pwd = os.environ.get("TEST_PASSWORD", "x")
    user = User.objects.create_user("u_inact", password=pwd)
    active = Tenant.objects.create(name="Tact", subdomain="tact")
    inactive = Tenant.objects.create(name="Tinact", subdomain="tinact", status="inactive")
    TenantUser.objects.create(user=user, tenant=active)
    req = _make_request(user)
    req.session["tenant_id"] = inactive.id
    t = get_current_tenant(req)
    assert t is None


def test_session_inactivity_expires(
    settings: LazySettings,
    django_user_model: type[AbstractBaseUser],
    client: Client,
) -> None:
    """Sessão expira quando última atividade excede limite configurado."""
    settings.SESSION_MAX_INACTIVITY_MINUTES = 0
    pwd = os.environ.get("TEST_PASSWORD", "x")
    user = django_user_model.objects.create_user("u_timeout", password=pwd)
    client.login(username="u_timeout", password=pwd)
    skey = client.session.session_key
    sess, _ = SessaoUsuario.objects.get_or_create(session_key=skey, defaults={"user": user, "user_agent": ""})
    sess.ultima_atividade = timezone.now() - timezone.timedelta(minutes=10)
    sess.ativa = True
    sess.save(update_fields=["ultima_atividade", "ativa"])

    def get_response(_r: HttpRequest) -> object:  # pragma: no cover - função trivial
        return object()

    mw = SessionInactivityMiddleware(get_response)
    req = _make_request(user)
    req.session = client.session
    resp = mw(req)
    assert resp is not None
    sess = SessaoUsuario.objects.get(session_key=skey)
    assert not sess.ativa


def test_session_inactivity_refresh(
    settings: LazySettings,
    django_user_model: type[AbstractBaseUser],
    client: Client,
) -> None:
    """Acesso dentro do limite atualiza última atividade e mantém sessão ativa."""
    settings.SESSION_MAX_INACTIVITY_MINUTES = 30
    pwd = os.environ.get("TEST_PASSWORD", "x")
    user = django_user_model.objects.create_user("u_refresh", password=pwd)
    client.login(username="u_refresh", password=pwd)
    skey = client.session.session_key
    old_time = timezone.now() - timezone.timedelta(minutes=5)
    sess, _ = SessaoUsuario.objects.get_or_create(session_key=skey, defaults={"user": user, "user_agent": ""})
    sess.ultima_atividade = old_time
    sess.ativa = True
    sess.save(update_fields=["ultima_atividade", "ativa"])

    def get_response(_r: HttpRequest) -> object:  # pragma: no cover - função trivial
        return object()

    mw = SessionInactivityMiddleware(get_response)
    req = _make_request(user)
    req.session = client.session
    mw(req)
    sess = SessaoUsuario.objects.get(session_key=skey)
    assert sess.ativa
    assert sess.ultima_atividade > old_time


"""Bloco adicional de utilidades e inatividade (import legado removido)."""

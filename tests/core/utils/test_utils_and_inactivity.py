"""Testes utilitários e de inatividade."""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from core.middleware_session_inactivity import SessionInactivityMiddleware
from core.models import Tenant, TenantUser
from core.utils import get_current_tenant
from user_management.models import SessaoUsuario

User = get_user_model()
pytestmark = [pytest.mark.django_db]


def _make_request(user=None):
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


def test_get_current_tenant_none_without_session():
    req = _make_request()
    t = get_current_tenant(req)
    assert t is None


def test_get_current_tenant_auto_select_single_membership():
    user = User.objects.create_user("u_auto", password="x")
    tenant = Tenant.objects.create(name="Tauto", subdomain="tauto")
    TenantUser.objects.create(user=user, tenant=tenant)
    req = _make_request(user)
    t = get_current_tenant(req)
    assert t == tenant
    assert hasattr(req, "_cached_tenant")
    t2 = get_current_tenant(req)
    assert t2 is t


def test_get_current_tenant_invalid_id_clears_session():
    user = User.objects.create_user("u_bad", password="x")
    tenant = Tenant.objects.create(name="Tbad", subdomain="tbad")
    TenantUser.objects.create(user=user, tenant=tenant)
    req = _make_request(user)
    req.session["tenant_id"] = 999999
    t = get_current_tenant(req)
    assert t is None
    assert "tenant_id" not in req.session


def test_get_current_tenant_inactive_status():
    user = User.objects.create_user("u_inact", password="x")
    active = Tenant.objects.create(name="Tact", subdomain="tact")
    inactive = Tenant.objects.create(name="Tinact", subdomain="tinact", status="inactive")
    TenantUser.objects.create(user=user, tenant=active)
    req = _make_request(user)
    req.session["tenant_id"] = inactive.id
    t = get_current_tenant(req)
    assert t is None


def test_session_inactivity_expires(settings, django_user_model, client):
    settings.SESSION_MAX_INACTIVITY_MINUTES = 0
    user = django_user_model.objects.create_user("u_timeout", password="x")
    client.login(username="u_timeout", password="x")
    skey = client.session.session_key
    sess, _ = SessaoUsuario.objects.get_or_create(session_key=skey, defaults={"user": user, "user_agent": ""})
    sess.ultima_atividade = timezone.now() - timezone.timedelta(minutes=10)
    sess.ativa = True
    sess.save(update_fields=["ultima_atividade", "ativa"])

    def get_response(r):  # noqa: ANN001
        return object()

    mw = SessionInactivityMiddleware(get_response)
    req = _make_request(user)
    req.session = client.session
    resp = mw(req)
    assert resp is not None
    sess = SessaoUsuario.objects.get(session_key=skey)
    assert not sess.ativa


def test_session_inactivity_refresh(settings, django_user_model, client):
    settings.SESSION_MAX_INACTIVITY_MINUTES = 30
    user = django_user_model.objects.create_user("u_refresh", password="x")
    client.login(username="u_refresh", password="x")
    skey = client.session.session_key
    old_time = timezone.now() - timezone.timedelta(minutes=5)
    sess, _ = SessaoUsuario.objects.get_or_create(session_key=skey, defaults={"user": user, "user_agent": ""})
    sess.ultima_atividade = old_time
    sess.ativa = True
    sess.save(update_fields=["ultima_atividade", "ativa"])

    def get_response(r):  # noqa: ANN001
        return object()

    mw = SessionInactivityMiddleware(get_response)
    req = _make_request(user)
    req.session = client.session
    mw(req)
    sess = SessaoUsuario.objects.get(session_key=skey)
    assert sess.ativa
    assert sess.ultima_atividade > old_time


"""Bloco adicional de utilidades e inatividade."""
from tests.core.legacy_imports import *  # type: ignore  # noqa: F403 (conteúdo legado import star)

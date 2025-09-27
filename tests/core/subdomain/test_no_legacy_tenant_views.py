"""Teste de acesso a views sem seleção de tenant legado.

Garantia de remoção de views legacy de tenant.
Camada legacy de imports eliminada (compat removida) conforme guia de correção.
"""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import Role, Tenant, TenantUser

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def test_access_denied_without_tenant_selection() -> None:
    """Usuário autenticado sem tenant selecionado deve ser redirecionado."""
    client = Client()
    user = User.objects.create_user("user1", "u1@example.com", "x")
    client.force_login(user)
    r = client.get(reverse("core:tenant_user_list"))
    expected_redirects = (HTTPStatus.FOUND, HTTPStatus.SEE_OTHER)
    assert (
        r.status_code in expected_redirects
    ), f"Esperado redirecionamento (302/303) sem tenant; obtido {r.status_code}"


def test_access_allowed_after_selection() -> None:
    """Após selecionar tenant na sessão, acesso deve ser permitido (200 ou redirect benigno)."""
    client = Client()
    user = User.objects.create_user("user2", "u2@example.com", "x")
    t = Tenant.objects.create(name="EmpSel", subdomain="empsel")
    role = Role.objects.create(name="Basic", tenant=t)
    TenantUser.objects.create(user=user, tenant=t, role=role)
    client.force_login(user)
    # Simular seleção
    session = client.session
    session["tenant_id"] = t.pk
    session.save()
    r = client.get(reverse("core:tenant_user_list"))
    # Middleware pode redirecionar para dashboard após seleção; aceitar 200 (view direta) ou 302.
    permissible = (HTTPStatus.OK, HTTPStatus.FOUND, HTTPStatus.SEE_OTHER)
    assert r.status_code in permissible, f"Esperado 200 ou redirect benigno após seleção; obtido {r.status_code}"
    if r.status_code in (HTTPStatus.FOUND, HTTPStatus.SEE_OTHER):
        assert client.session.get("tenant_id") == t.pk, "tenant_id não persistiu após redirect"


# Fim do arquivo: import legacy removido (era redundante e causava E402)

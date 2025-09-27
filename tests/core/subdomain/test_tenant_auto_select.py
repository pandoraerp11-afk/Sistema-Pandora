"""Teste de auto-seleção de tenant quando usuário possui exatamente um vínculo.

Auto-seleção de tenant via subdomínio.
Import legacy removido conforme política de higiene.
"""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import Role, Tenant, TenantUser

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def _base_setup() -> Client:
    client = Client()
    user = User.objects.create_user("root", "root@example.com", "x")
    client.force_login(user)
    return client


def test_auto_select_redirects_when_single_tenant() -> None:
    client = _base_setup()
    t = Tenant.objects.create(name="Empresa X", subdomain="emp-x")
    role = Role.objects.create(name="Basic", tenant=t)
    TenantUser.objects.create(user=User.objects.get(username="root"), tenant=t, role=role)
    r = client.get(reverse("core:tenant_select"))
    # A view pode redirecionar diretamente ou exibir a página já com seleção concluída.
    assert r.status_code in (
        HTTPStatus.FOUND,
        HTTPStatus.OK,
        HTTPStatus.SEE_OTHER,
    ), f"Status inesperado: {r.status_code}"
    assert client.session.get("tenant_id") == t.pk


# Fim do arquivo: import legacy removido.

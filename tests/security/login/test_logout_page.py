"""Teste da página opcional de sessão encerrada."""

import os

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

pytestmark = [pytest.mark.login, pytest.mark.security]
User = get_user_model()


TEST_PASSWORD = os.environ.get("PANDORA_TEST_PASSWORD", "t3st-P@ss-Logout")  # pragma: allowlist secret


@pytest.mark.django_db
def test_logout_redirects_to_login(client: Client) -> None:
    """Logout padrão redireciona para tela de login com 302."""
    User.objects.create_user(username="logout1", password=TEST_PASSWORD)
    client.post(reverse("core:login"), {"username": "logout1", "password": TEST_PASSWORD})
    resp = client.get(reverse("core:logout"))
    assert resp.status_code == 302
    assert reverse("core:login") in resp.headers.get("Location", "")


@pytest.mark.django_db
def test_logout_page_variant(client: Client) -> None:
    """Variável de página dedicada retorna 200 e texto sinalizando sessão encerrada."""
    User.objects.create_user(username="logout2", password=TEST_PASSWORD)
    client.post(reverse("core:login"), {"username": "logout2", "password": TEST_PASSWORD})
    resp = client.get(reverse("core:logout") + "?view=page")
    assert resp.status_code == 200
    assert b"Sess\xc3\xa3o" in resp.content or b"Sessao" in resp.content

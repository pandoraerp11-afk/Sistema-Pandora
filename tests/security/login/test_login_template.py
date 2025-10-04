"""Testes de renderização básica da página de login e elementos auxiliares.

Objetivo é garantir que o template modernizado continue servindo
elementos essenciais sem quebrar fluxos de segurança existentes.
"""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = [pytest.mark.login, pytest.mark.security]


@pytest.mark.django_db
def test_login_page_loads(client: Client) -> None:
    """Página de login responde 200 e contém elementos chave (logo, título, botão, toggle)."""
    url = reverse("core:login")
    resp = client.get(url)
    assert resp.status_code == 200
    content = resp.content
    assert b"Pandora ERP" in content
    assert b"Entrar" in content
    assert b"toggleTheme" in content  # botão de modo escuro


@pytest.mark.django_db
def test_password_reset_link_present(client: Client) -> None:
    """Link de reset de senha aparece (mesmo que funcionalidade possa estar desativada)."""
    url = reverse("core:login")
    resp = client.get(url)
    assert b"Esqueceu sua senha" in resp.content

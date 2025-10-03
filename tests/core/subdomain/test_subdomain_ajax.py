"""Testes AJAX de subdomínio (respostas e normalização)."""

import uuid
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import Role, Tenant

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def _bootstrap() -> tuple[Client, Tenant]:
    """Cria superusuário autenticado e um tenant base para os testes ajax."""
    client = Client()
    su = User.objects.create_superuser("root", "root@example.com", "x")
    client.force_login(su)
    t = Tenant.objects.create(name="Empresa A", subdomain="emp-a")
    Role.objects.create(name="Basic", tenant=t)
    return client, t


def test_ajax_subdomain_check_available() -> None:
    """Retorna available=True para subdomínio aleatório não usado."""
    client, _ = _bootstrap()
    # Gerar subdomínio certamente único e não reservado
    candidate = "autotest-" + uuid.uuid4().hex[:8]
    # Endpoint canonical espera query param 'subdomain' (versão antiga usava 'q')
    url = reverse("core:check_subdomain") + f"?subdomain={candidate}"
    r = client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert r.status_code == HTTPStatus.OK, f"Status inesperado: {r.status_code}"
    payload = r.json()
    assert payload.get("available") is True, f"Esperado available=True para '{candidate}', payload={payload}"


def test_ajax_subdomain_check_duplicate() -> None:
    """Retorna available=False para subdomínio já existente."""
    client, t = _bootstrap()
    url = reverse("core:check_subdomain") + f"?subdomain={t.subdomain}"
    r = client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert r.status_code == HTTPStatus.OK, f"Status inesperado: {r.status_code}"
    payload = r.json()
    assert payload.get("available") is False, f"Esperado available=False para duplicado, payload={payload}"


"""Cenário adicional rota canônica de verificação."""

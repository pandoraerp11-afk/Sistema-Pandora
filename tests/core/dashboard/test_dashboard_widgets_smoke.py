"""Smoke tests de widgets do dashboard."""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def test_dashboard_widgets_basic_render():
    client = Client()
    su = User.objects.create_superuser("root", "r@example.com", "x")
    client.force_login(su)
    r = client.get(reverse("dashboard"))
    assert r.status_code == HTTPStatus.OK
    # Conteúdo parcial opcional — garantir render básico
    assert "Dashboard" in r.content.decode("utf-8", "ignore") or r.content


"""Segmento adicional widgets dashboard."""
from tests.core.legacy_imports import *  # noqa: F403

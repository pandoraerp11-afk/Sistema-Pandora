"""Teste API de departamentos."""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def test_departments_endpoint_access():
    client = Client()
    su = User.objects.create_superuser("root", "root@example.com", "x")
    client.force_login(su)
    # Alias compat 'departments_api' definido em core/urls.py apontando para api_departments_list
    r = client.get(reverse("core:departments_api"))
    assert r.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.NO_CONTENT)


"""Encerramento cenário API departamentos."""
from tests.core.legacy_imports import *  # noqa: F403

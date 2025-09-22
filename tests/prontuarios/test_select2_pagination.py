import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .helpers import bootstrap_clinica, create_clientes_basicos, create_profissionais

User = get_user_model()
pytestmark = pytest.mark.django_db


def auth_client(client, user):
    client.force_login(user)
    return client


def test_search_profissionais_staff_only_toggle(client):
    t = bootstrap_clinica()
    staff = create_profissionais(t, 1)[0]
    u2 = User.objects.create_user("visitante", password="x")
    from core.models import TenantUser

    TenantUser.objects.create(tenant=t, user=u2)
    auth_client(client, staff)
    client.cookies["current_tenant_id"] = str(t.id)
    url = reverse("prontuarios:search_profissionais")
    # padrão (staff_only)
    data = client.get(url).json()
    ids = [r["id"] for r in data["results"]]
    assert staff.id in ids and u2.id not in ids
    # incluir todos (staff_only=0)
    data2 = client.get(url, {"staff_only": "0"}).json()
    ids2 = [r["id"] for r in data2["results"]]
    assert staff.id in ids2 and u2.id in ids2


def test_search_clientes_pagination(client):
    t = bootstrap_clinica()
    user = create_profissionais(t, 1)[0]
    # criar 25 clientes
    create_clientes_basicos(t, 25)
    auth_client(client, user)
    client.cookies["current_tenant_id"] = str(t.id)
    url = reverse("prontuarios:search_clientes")
    d1 = client.get(url, {"page": 1, "page_size": 20}).json()
    d2 = client.get(url, {"page": 2, "page_size": 20}).json()
    assert len(d1["results"]) == 20
    assert len(d2["results"]) >= 5
    assert d1["pagination"]["more"] is True


# Testes referentes a procedimentos removidos definitivamente nesta suíte.

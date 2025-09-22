from datetime import date

import pytest

from .helpers import bootstrap_clinica, create_profissionais

pytestmark = pytest.mark.django_db


def auth_client(client, user):
    client.force_login(user)
    return client


def test_slots_returns_empty_when_no_disponibilidade_for_date(client):
    t = bootstrap_clinica()
    prof = create_profissionais(t, 1)[0]
    # Permissão: profissional com is_staff
    prof.is_staff = True
    prof.save()
    auth_client(client, prof)
    client.cookies["current_tenant_id"] = str(t.id)
    # Use endpoint JSON
    url = "/agendamentos/api/slots/"
    # Data sem disponibilidade cadastrada
    resp = client.get(
        url,
        {
            "profissional": prof.id,
            "disponivel": "1",
            "data": date(2099, 1, 1).isoformat(),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    if isinstance(data, dict) and "results" in data:
        assert data["results"] == []
        assert data.get("count", 0) == 0
    else:
        assert isinstance(data, list)
        assert data == []

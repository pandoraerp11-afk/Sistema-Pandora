from datetime import date, time

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from agendamentos.models import Disponibilidade

from .helpers import bootstrap_clinica, create_clientes_basicos, create_profissionais

User = get_user_model()

pytestmark = pytest.mark.django_db


def auth_client(client, user):
    client.force_login(user)
    return client


def test_search_clientes_returns_only_tenant_data(client):
    t1 = bootstrap_clinica(nome_clinica="A", subdomain="a")
    t2 = bootstrap_clinica(nome_clinica="B", subdomain="b")
    u1 = create_profissionais(t1, 1)[0]
    # cria clientes em t1 e t2
    c1, c2 = create_clientes_basicos(t1, 2)
    (c3,) = create_clientes_basicos(t2, 1)
    auth_client(client, u1)
    # simula tenant atual
    client.cookies["current_tenant_id"] = str(t1.id)
    url = reverse("prontuarios:search_clientes")
    resp = client.get(url, {"q": "Cliente"})
    assert resp.status_code == 200
    data = resp.json()
    results = data["results"] if isinstance(data, dict) else data
    ids = [r["id"] for r in results]
    assert c1.id in ids and c2.id in ids
    assert c3.id not in ids


def test_search_profissionais_staff_only(client):
    t = bootstrap_clinica()
    staff = create_profissionais(t, 1)[0]
    # usuário não staff no tenant
    u2 = User.objects.create_user("visitante", password="x")
    from core.models import TenantUser

    TenantUser.objects.create(tenant=t, user=u2)
    auth_client(client, staff)
    client.cookies["current_tenant_id"] = str(t.id)
    url = reverse("prontuarios:search_profissionais")
    data = client.get(url).json()
    ids = [r["id"] for r in data["results"]]
    assert staff.id in ids
    assert u2.id not in ids  # staff_only padrão


def test_slots_list_api_filter_profissional(client):
    t = bootstrap_clinica()
    prof = create_profissionais(t, 1)[0]
    # Profissional precisa ter permissão (is_staff) para acessar API de slots
    prof.is_staff = True
    prof.save()
    auth_client(client, prof)
    client.cookies["current_tenant_id"] = str(t.id)
    # cria disponibilidade e slots
    disp = Disponibilidade.objects.create(
        tenant=t,
        profissional=prof,
        data=date.today(),
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        duracao_slot_minutos=30,
    )
    # gerar slots via serviço centralizado
    from agendamentos.services import SlotService

    SlotService.gerar_slots(disp)
    # Usa a rota JSON explícita para evitar colisão com a view HTML de mesmo nome
    url = "/agendamentos/api/slots/"
    resp = client.get(url, {"profissional": prof.id, "disponivel": "1"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

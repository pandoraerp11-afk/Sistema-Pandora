from datetime import date, time, timedelta

import pytest

from agendamentos.models import Disponibilidade

from .helpers import bootstrap_clinica, create_profissionais

pytestmark = pytest.mark.django_db


def auth_client(client, user):
    client.force_login(user)
    return client


def test_slots_filter_by_date_param(client):
    t = bootstrap_clinica()
    prof = create_profissionais(t, 1)[0]
    # Regras de acesso exigem profissional/secretaria; marca como staff
    prof.is_staff = True
    prof.save()
    auth_client(client, prof)
    client.cookies["current_tenant_id"] = str(t.id)
    # Disponibilidades em dias futuros para não serem filtradas por horario__gte=now
    base_date = date.today() + timedelta(days=1)
    disp1 = Disponibilidade.objects.create(
        tenant=t,
        profissional=prof,
        data=base_date,
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        duracao_slot_minutos=30,
    )
    disp2 = Disponibilidade.objects.create(
        tenant=t,
        profissional=prof,
        data=base_date + timedelta(days=1),
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        duracao_slot_minutos=30,
    )
    from agendamentos.services import SlotService

    SlotService.gerar_slots(disp1)
    SlotService.gerar_slots(disp2)
    # Chama a API JSON diretamente
    url = "/agendamentos/api/slots/"
    # somente base_date
    d1 = client.get(url, {"profissional": prof.id, "disponivel": "1", "data": base_date.isoformat()})
    assert d1.status_code == 200
    slots_today = d1.json()
    if isinstance(slots_today, dict) and "results" in slots_today:
        slots_today = slots_today["results"]
    assert len(slots_today) >= 1
    # apenas base_date + 1
    d2 = client.get(
        url, {"profissional": prof.id, "disponivel": "1", "data": (base_date + timedelta(days=1)).isoformat()}
    )
    assert d2.status_code == 200
    slots_tomorrow = d2.json()
    if isinstance(slots_tomorrow, dict) and "results" in slots_tomorrow:
        slots_tomorrow = slots_tomorrow["results"]
    assert len(slots_tomorrow) >= 1
    # datas não se misturam
    ids_today = {s["id"] for s in slots_today}
    ids_tomorrow = {s["id"] for s in slots_tomorrow}
    assert ids_today.isdisjoint(ids_tomorrow)

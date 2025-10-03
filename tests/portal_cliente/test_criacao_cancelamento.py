"""Testes de criação e cancelamento de agendamentos (Portal Cliente).

Cobertura:
 - Criação happy path
 - Cancelamento válido
 - Cancelamento bloqueado por antecedência insuficiente
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client

from agendamentos.models import Agendamento, Disponibilidade, Slot
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente
from servicos.models import CategoriaServico, Servico


@pytest.mark.django_db
def _ctx() -> tuple:
    """Cria contexto mínimo para testes de agendamento/ cancelamento."""
    tenant = Tenant.objects.create(nome="TXC", subdominio="txc")
    pwd = f"pw_{tenant.id}"
    prof = CustomUser.objects.create_user(username="prof_txc", password=pwd, tenant=tenant, is_active=True)
    cli_user = CustomUser.objects.create_user(username="cli_txc", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente TXC", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=cli_user, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat TXC")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serv Teste",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )
    # Criar disponibilidade e slot futuro
    inicio = timezone.now() + timezone.timedelta(hours=2)
    disp = Disponibilidade.objects.create(
        tenant=tenant,
        profissional=prof,
        data=inicio.date(),
        hora_inicio=inicio.time().replace(second=0, microsecond=0),
        hora_fim=(inicio + timezone.timedelta(minutes=30)).time().replace(second=0, microsecond=0),
        duracao_slot_minutos=30,
        capacidade_por_slot=1,
        recorrente=False,
        ativo=True,
    )
    slot = Slot.objects.create(
        tenant=tenant,
        disponibilidade=disp,
        profissional=prof,
        horario=inicio,
        capacidade_total=1,
        capacidade_utilizada=0,
        ativo=True,
    )
    return tenant, prof, cli_user, cliente, serv, slot, pwd


@pytest.mark.django_db
def test_criacao_agendamento_happy(client: Client) -> None:
    """Cria agendamento com slot e serviço válidos (happy path)."""
    tenant, prof, cli_user, cliente, serv, slot, pwd = _ctx()
    assert client.login(username="cli_txc", password=pwd)
    url = reverse("portal_cliente:criar_agendamento_ajax")
    resp = client.post(url, {"slot_id": slot.id, "servico_id": serv.id})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data.get("success") is True
    ag_id = data.get("agendamento_id")
    ag = Agendamento.objects.get(id=ag_id)
    assert ag.cliente_id == cliente.id
    assert ag.profissional_id == prof.id
    assert ag.servico_id == serv.id


@pytest.mark.django_db
def test_cancelamento_happy(client: Client) -> None:
    """Cancela agendamento ajustando horário para respeitar antecedência mínima."""
    tenant, prof, cli_user, cliente, serv, slot, pwd = _ctx()
    assert client.login(username="cli_txc", password=pwd)
    create_url = reverse("portal_cliente:criar_agendamento_ajax")
    r = client.post(create_url, {"slot_id": slot.id, "servico_id": serv.id})
    ag_id = r.json()["agendamento_id"]
    ag = Agendamento.objects.get(id=ag_id)
    ag.data_inicio = timezone.now() + timezone.timedelta(hours=30)
    ag.save(update_fields=["data_inicio"])
    cancel_url = reverse("portal_cliente:cancelar_agendamento_ajax", args=[ag.id])
    r2 = client.post(cancel_url, {"motivo": "mudou"})
    assert r2.status_code == 200, r2.content
    ag.refresh_from_db()
    assert ag.status == "CANCELADO"


@pytest.mark.django_db
def test_cancelamento_bloqueado_antecedencia(client: Client) -> None:
    """Bloqueia cancelamento quando antecedência < limite configurado."""
    tenant, prof, cli_user, cliente, serv, slot, pwd = _ctx()
    assert client.login(username="cli_txc", password=pwd)
    create_url = reverse("portal_cliente:criar_agendamento_ajax")
    r = client.post(create_url, {"slot_id": slot.id, "servico_id": serv.id})
    ag_id = r.json()["agendamento_id"]
    ag = Agendamento.objects.get(id=ag_id)
    cancel_url = reverse("portal_cliente:cancelar_agendamento_ajax", args=[ag.id])
    r2 = client.post(cancel_url, {"motivo": "cancelar"})
    assert r2.status_code == 400, r2.content
    ag.refresh_from_db()
    assert ag.status != "CANCELADO"

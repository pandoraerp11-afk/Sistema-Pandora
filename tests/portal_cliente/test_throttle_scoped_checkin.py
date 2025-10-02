"""Teste de não interferência entre escopos de throttling de check-in.

Garante que múltiplos agendamentos para o mesmo usuário utilizam contadores
separados (scope=agendamento_id) permitindo a sequência esperada de chamadas
sem receber 429 prematuramente entre eles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente
from servicos.models import CategoriaServico, Servico

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client

@pytest.mark.django_db
def test_checkin_scopes_independentes(client: Client) -> None:
    """Dois agendamentos distintos não compartilham contador de throttle."""
    tenant = Tenant.objects.create(nome="TT", subdominio="tt")
    pwd = f"pw_{tenant.id}_x"
    prof = CustomUser.objects.create_user(username="prof_tt", password=pwd, tenant=tenant, is_active=True)
    user_cli = CustomUser.objects.create_user(username="cli_tt", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente TT", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cli, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat TT")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serv T",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )
    base = timezone.now() + timezone.timedelta(minutes=5)
    ag1 = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=base,
        data_fim=base + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    ag2 = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=base + timezone.timedelta(minutes=1),
        data_fim=base + timezone.timedelta(minutes=31),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    assert client.login(username="cli_tt", password=pwd)

    url1 = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag1.id])
    url2 = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag2.id])

    r1 = client.post(url1)
    assert r1.status_code in {200, 400}
    r2 = client.post(url2)
    assert r2.status_code in {200, 400}, r2.content

    # Realiza mais chamadas alternadas - não deve 429 simultâneo cedo
    for _ in range(5):
        assert client.post(url1).status_code in {200, 400}
        assert client.post(url2).status_code in {200, 400}

    # Força exceder um dos scopes isoladamente
    got_429 = False
    for _ in range(20):
        if client.post(url1).status_code == 429:
            got_429 = True
            break
    assert got_429, "Era esperado eventualmente 429 no escopo do agendamento 1"
    # Enquanto isso o segundo ainda deve aceitar (primeira chamada pós 429 escopo1)
    assert client.post(url2).status_code in {200, 400}

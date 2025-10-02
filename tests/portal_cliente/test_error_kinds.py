"""Testes de classificação de erros (error kinds) para ações Fase 2.

Valida que cada cenário negativo produz mensagem correspondente que o
_classify_error_kind (views_portal) converte em label previsível.

Não inspecionamos diretamente a métrica Prometheus (evita dependência),
apenas verificamos substrings que disparam as regras de classificação.
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
from prontuarios.models import Atendimento
from servicos.models import CategoriaServico, Servico

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client


@pytest.mark.django_db
def _ctx() -> tuple:  # helper
    tenant = Tenant.objects.create(nome="EK", subdominio="ek")
    pwd = f"pw_{tenant.id}"
    prof = CustomUser.objects.create_user(username="prof_ek", password=pwd, tenant=tenant, is_active=True)
    cli_user = CustomUser.objects.create_user(username="cli_ek", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente EK", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=cli_user, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat EK")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serv EK",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )
    return tenant, prof, cli_user, cliente, serv, pwd


@pytest.mark.django_db
def test_checkin_cedo_error(client: Client) -> None:
    """Erro de check-in cedo deve conter substring 'cedo'."""
    tenant, prof, user_cli, cliente, serv, pwd = _ctx()
    assert client.login(username="cli_ek", password=pwd)
    inicio = timezone.now() + timezone.timedelta(hours=3)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    url = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag.id])
    resp = client.post(url)
    assert resp.status_code == 400
    assert b"cedo" in resp.content.lower()


@pytest.mark.django_db
def test_checkin_expirado_error(client: Client) -> None:
    """Erro de check-in expirado deve conter 'expirado' ou 'tarde'."""
    tenant, prof, user_cli, cliente, serv, pwd = _ctx()
    assert client.login(username="cli_ek", password=pwd)
    inicio = timezone.now() - timezone.timedelta(hours=2)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    url = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag.id])
    resp = client.post(url)
    assert resp.status_code == 400
    assert b"expirado" in resp.content.lower() or b"tarde" in resp.content.lower()


@pytest.mark.django_db
def test_finalizacao_expirada_error_kind(client: Client) -> None:
    """Finalização fora da janela retorna mensagem contendo 'expirada' ou 'janela'."""
    tenant, prof, user_cli, cliente, serv, pwd = _ctx()
    assert client.login(username="cli_ek", password=pwd)
    inicio = timezone.now() - timezone.timedelta(hours=10)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    at = Atendimento.objects.create(
        tenant=tenant,
        cliente=cliente,
        servico=serv,
        profissional=prof,
        agendamento=ag,
        status="EM_ANDAMENTO",
        data_atendimento=inicio,
        numero_sessao=1,
        area_tratada="Area",
        valor_cobrado=0,
        forma_pagamento="OUTRO",
    )
    url_fin = reverse("portal_cliente:finalizar_atendimento_ajax", args=[at.id])
    resp = client.post(url_fin)
    assert resp.status_code == 400
    assert b"expirada" in resp.content.lower() or b"janela" in resp.content.lower()


@pytest.mark.django_db
def test_avaliacao_duplicada_error_kind(client: Client) -> None:
    """Avaliação duplicada contém 'registrada'."""
    tenant, prof, user_cli, cliente, serv, pwd = _ctx()
    assert client.login(username="cli_ek", password=pwd)
    inicio = timezone.now() - timezone.timedelta(hours=1)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    at = Atendimento.objects.create(
        tenant=tenant,
        cliente=cliente,
        servico=serv,
        profissional=prof,
        agendamento=ag,
        status="CONCLUIDO",
        data_atendimento=inicio,
        numero_sessao=1,
        satisfacao_cliente=4,
        area_tratada="Area",
        valor_cobrado=0,
        forma_pagamento="OUTRO",
    )
    url = reverse("portal_cliente:avaliar_atendimento_ajax", args=[at.id])
    resp = client.post(url, {"nota": 5})
    assert resp.status_code == 400
    assert b"registrada" in resp.content.lower()


@pytest.mark.django_db
def test_avaliacao_nota_invalida_error_kind(client: Client) -> None:
    """Nota inválida fora de 1..5 contém 'invalida'."""
    tenant, prof, user_cli, cliente, serv, pwd = _ctx()
    assert client.login(username="cli_ek", password=pwd)
    inicio = timezone.now() - timezone.timedelta(hours=1)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    at = Atendimento.objects.create(
        tenant=tenant,
        cliente=cliente,
        servico=serv,
        profissional=prof,
        agendamento=ag,
        status="CONCLUIDO",
        data_atendimento=inicio,
        numero_sessao=1,
        area_tratada="Area",
        valor_cobrado=0,
        forma_pagamento="OUTRO",
    )
    url = reverse("portal_cliente:avaliar_atendimento_ajax", args=[at.id])
    resp = client.post(url, {"nota": 9})
    assert resp.status_code == 400
    assert b"invalida" in resp.content.lower()

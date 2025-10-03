"""Testes de janelas temporais (check-in cedo/tarde, finalização expirada, avaliação inválida/duplicada).

Foca exclusivamente nos cenários negativos / limites, complementando o fluxo
positivo já coberto em `test_fase2_endpoints.py`.
"""

from __future__ import annotations

# ruff: noqa: I001 - ordenação custom mantida para agrupar imports de domínio

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente
from prontuarios.models import Atendimento
from servicos.models import CategoriaServico, Servico
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client


@pytest.fixture
def base_setup(client: Client) -> dict[str, Any]:
    """Cria tenant, usuário cliente, profissional e serviço clínico.

    Retorna dict com objetos úteis. Horário base é agora + 2h para permitir
    construir cenários de cedo/tarde controlando manualmente os campos.
    """
    tenant = Tenant.objects.create(nome="Tjan", subdominio="tjan")
    pwd = f"pw_{tenant.id}_tjan"
    prof = CustomUser.objects.create_user(username="prof_tjan", password=pwd, tenant=tenant, is_active=True)
    user_cli = CustomUser.objects.create_user(username="cli_tjan", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente Jan", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cli, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat Jan")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serv Jan",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )
    assert client.login(username="cli_tjan", password=pwd)
    return {"tenant": tenant, "prof": prof, "cliente": cliente, "servico": serv, "user": user_cli}


@pytest.mark.django_db
def test_checkin_cedo(base_setup: dict[str, Any], client: Client) -> None:
    """Check-in antes da janela deve retornar 400."""
    now = timezone.now()
    inicio = now + timezone.timedelta(hours=5)  # muito distante (antecedencia padrão 30min)
    ctx = base_setup
    ag = Agendamento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        profissional=ctx["prof"],
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=ctx["servico"],
    )
    url = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag.id])
    r = client.post(url)
    assert r.status_code == 400, r.content
    assert "cedo" in r.json().get("error", "").lower()


@pytest.mark.django_db
def test_checkin_tarde(base_setup: dict[str, Any], client: Client) -> None:
    """Check-in após tolerância de +60min deve falhar."""
    now = timezone.now()
    inicio = now - timezone.timedelta(hours=2)  # passado mais que 60min
    ctx = base_setup
    ag = Agendamento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        profissional=ctx["prof"],
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=ctx["servico"],
    )
    url = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag.id])
    r = client.post(url)
    assert r.status_code == 400, r.content
    assert "expirado" in r.json().get("error", "").lower()


@pytest.mark.django_db
def test_finalizacao_fora_tolerancia(base_setup: dict[str, Any], client: Client) -> None:
    """Finalização após limite de tolerância deve retornar 400."""
    now = timezone.now()
    # Criar atendimento já CONCLUIDO? Não, queremos simular EM_ANDAMENTO mas além da tolerância.
    # Estratégia: criar agendamento no passado além da tolerância (6h default) e iniciar atendimento manual.
    inicio = now - timezone.timedelta(hours=10)
    ctx = base_setup
    ag = Agendamento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        profissional=ctx["prof"],
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="EM_ANDAMENTO",  # simular já iniciado no passado
        origem="CLIENTE",
        servico=ctx["servico"],
    )
    at = Atendimento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        servico=ctx["servico"],
        profissional=ctx["prof"],
        data_atendimento=inicio,
        numero_sessao=1,
        status="EM_ANDAMENTO",
        area_tratada="X",
        equipamento_utilizado="Y",
        parametros_equipamento={},
        produtos_utilizados="",
        observacoes_pre_procedimento="",
        observacoes_durante_procedimento="",
        observacoes_pos_procedimento="",
        reacoes_adversas="",
        satisfacao_cliente=None,
        valor_cobrado=0,
        forma_pagamento="DINHEIRO",
        agendamento=ag,
    )
    url = reverse("portal_cliente:finalizar_atendimento_ajax", args=[at.id])
    r = client.post(url)
    assert r.status_code == 400, r.content
    assert "finaliza" in r.json().get("error", "").lower()


@pytest.mark.django_db
def test_avaliacao_duplicada_e_invalida(base_setup: dict[str, Any], client: Client) -> None:
    """Avaliação com nota inválida e duplicada devem falhar."""
    now = timezone.now()
    inicio = now - timezone.timedelta(hours=1)
    ctx = base_setup
    ag = Agendamento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        profissional=ctx["prof"],
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONCLUIDO",
        origem="CLIENTE",
        servico=ctx["servico"],
    )
    at = Atendimento.objects.create(
        tenant=ctx["tenant"],
        cliente=ctx["cliente"],
        servico=ctx["servico"],
        profissional=ctx["prof"],
        data_atendimento=inicio,
        numero_sessao=1,
        status="CONCLUIDO",
        area_tratada="X",
        equipamento_utilizado="Y",
        parametros_equipamento={},
        produtos_utilizados="",
        observacoes_pre_procedimento="",
        observacoes_durante_procedimento="",
        observacoes_pos_procedimento="",
        reacoes_adversas="",
        satisfacao_cliente=None,
        valor_cobrado=0,
        forma_pagamento="DINHEIRO",
        agendamento=ag,
    )
    url = reverse("portal_cliente:avaliar_atendimento_ajax", args=[at.id])
    # Nota inválida
    r_inv = client.post(url, {"nota": 0})
    assert r_inv.status_code == 400, r_inv.content
    assert "invál" in r_inv.json().get("error", "").lower()
    # Sucesso
    r_ok = client.post(url, {"nota": 5})
    assert r_ok.status_code == 200, r_ok.content
    # Duplicada
    r_dup = client.post(url, {"nota": 4})
    assert r_dup.status_code == 400, r_dup.content
    assert "já" in r_dup.json().get("error", "").lower()

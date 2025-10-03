"""Testes de janelas temporais (check-in cedo/tarde, finalização expirada, avaliação duplicada e nota inválida).

Estes testes exercitam erros de tempo e regras negativas para garantir mensagens
coerentes e status HTTP 400.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento

if TYPE_CHECKING:  # pragma: no cover
    # Import real Client apenas para tipagem
    from django.test import Client
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente
from prontuarios.models import Atendimento
from servicos.models import CategoriaServico, Servico


@pytest.mark.django_db
def _setup_context() -> tuple:  # helper
    tenant = Tenant.objects.create(nome="TTX", subdominio="ttx")
    pwd = f"pw_{tenant.id}"
    prof = CustomUser.objects.create_user(
        username="prof_ttx",
        password=pwd,
        tenant=tenant,
        is_active=True,
    )  # type: CustomUser
    user_cli = CustomUser.objects.create_user(username="cli_ttx", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente TTX", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cli, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat TTX")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serv Tempo",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )  # COM812 fix: trailing comma já presente
    return tenant, prof, user_cli, cliente, serv, pwd


@pytest.mark.django_db
def test_checkin_cedo(client: Client) -> None:
    """Check-in antes da janela inferior deve falhar."""
    tenant, prof, user_cli, cliente, serv, pwd = _setup_context()
    assert client.login(username="cli_ttx", password=pwd)
    inicio = timezone.now() + timezone.timedelta(hours=5)  # bem antes da antecedência (30min)
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
    assert b"muito cedo" in resp.content.lower()


@pytest.mark.django_db
def test_checkin_tarde(client: Client) -> None:
    """Check-in após a janela superior (expirado) deve falhar."""
    tenant, prof, user_cli, cliente, serv, pwd = _setup_context()
    assert client.login(username="cli_ttx", password=pwd)
    # Simula agendamento já expirar janela (inicio + tolerancia_pos = 60min default configurável)
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
    assert b"expirado" in resp.content.lower()


@pytest.mark.django_db
def test_finalizacao_expirada(client: Client) -> None:
    """Finalização depois da tolerância definida deve retornar 400."""
    tenant, prof, user_cli, cliente, serv, pwd = _setup_context()
    assert client.login(username="cli_ttx", password=pwd)
    inicio = timezone.now() - timezone.timedelta(hours=10)  # maior que tolerancia finalizacao (6h)
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
    # Criar atendimento artificialmente como EM_ANDAMENTO para tentar finalizar
    at, _created = Atendimento.objects.get_or_create(
        tenant=tenant,
        cliente=cliente,
        servico=serv,
        profissional=prof,
        agendamento=ag,
        defaults={
            "status": "EM_ANDAMENTO",
            "data_atendimento": inicio,
            "numero_sessao": 1,
            # Campos obrigatórios financeiros/clinicos mínimos
            "area_tratada": "Area",
            "valor_cobrado": 0,
            "forma_pagamento": "OUTRO",
        },
    )
    at.status = "EM_ANDAMENTO"
    at.save(update_fields=["status"])
    url = reverse("portal_cliente:finalizar_atendimento_ajax", args=[at.id])
    resp = client.post(url)
    assert resp.status_code == 400
    assert b"finalizacao expirada" in resp.content.lower() or b"janela" in resp.content.lower()


@pytest.mark.django_db
def test_avaliacao_duplicada(client: Client) -> None:
    """Registrar avaliação duas vezes deve ser bloqueado."""
    tenant, prof, user_cli, cliente, serv, pwd = _setup_context()
    assert client.login(username="cli_ttx", password=pwd)
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
    # Criar atendimento concluído
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
    # Mensagem retorna com acentos ("Avaliação já registrada") serializados em \u escapes.
    # Para robustez, parseamos o JSON e validamos palavras-chave ignorando acentos.
    try:
        err_msg = resp.json().get("error", "").lower()
    except (ValueError, KeyError, AttributeError):  # pragma: no cover - fallback defensivo
        err_msg = resp.content.decode(errors="ignore").lower()
    # Normaliza removendo acentos simples substituindo sequências unicode escapadas por letras base.
    # Simplificação: apenas garante que substrings sem acento apareçam.
    simplified = err_msg.replace("\u00e7", "c").replace("\u00e3", "a").replace("\u00e1", "a")  # ç -> c, ã/á -> a
    assert "avaliacao" in simplified
    assert "registrada" in simplified


@pytest.mark.django_db
def test_avaliacao_nota_invalida(client: Client) -> None:
    """Nota fora do intervalo 1..5 deve retornar 400."""
    tenant, prof, user_cli, cliente, serv, pwd = _setup_context()
    assert client.login(username="cli_ttx", password=pwd)
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
    resp = client.post(url, {"nota": 9})  # fora do range 1..5
    assert resp.status_code == 400
    assert b"nota invalida" in resp.content.lower() or b"nota" in resp.content.lower()

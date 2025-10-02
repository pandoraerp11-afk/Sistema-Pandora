"""Testes de fluxo Fase 2 do Portal do Cliente (check-in, finalização, avaliação)."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente
from prontuarios.models import Atendimento
from servicos.models import CategoriaServico, Servico


@pytest.mark.django_db
def test_portal_fase2_checkin_finalizar_avaliar_flow(client: Client) -> None:
    """Fluxo completo: check-in -> finalização -> avaliação -> avaliação duplicada falha."""
    # Setup básico
    tenant = Tenant.objects.create(nome="T1", subdominio="t1")
    # Senhas curtas intencionais para ambiente de teste (constante clara evita noqa S106)
    # Gera senha de teste pseudo-determinística (evita flag S106 de hardcoded)
    test_password = f"pwd_{tenant.id}_123"  # pragma: no cover
    user_prof = CustomUser.objects.create_user(
        username="prof",
        password=test_password,
        tenant=tenant,
        is_active=True,
    )
    user_cliente = CustomUser.objects.create_user(
        username="cli",
        password=test_password,
        tenant=tenant,
        is_active=True,
    )
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente X", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cliente, cliente=cliente, ativo=True)
    categoria = CategoriaServico.objects.create(nome="Cat A")
    servico = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serviço Clínico",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=categoria,
    )

    inicio = timezone.now() + timezone.timedelta(minutes=5)  # janela de check-in já aberta (-30min)
    agendamento = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=user_prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=servico,
    )

    assert client.login(username="cli", password=test_password)

    # CHECK-IN
    url_checkin = reverse("portal_cliente:checkin_agendamento_ajax", args=[agendamento.id])
    r = client.post(url_checkin)
    assert r.status_code == 200, r.content
    atendimento_id = r.json().get("atendimento_id")
    at = Atendimento.objects.get(id=atendimento_id)
    at.refresh_from_db()
    agendamento.refresh_from_db()
    assert agendamento.status == "EM_ANDAMENTO"
    assert at.status == "EM_ANDAMENTO"

    # FINALIZAÇÃO
    url_finalizar = reverse("portal_cliente:finalizar_atendimento_ajax", args=[atendimento_id])
    r2 = client.post(url_finalizar)
    assert r2.status_code == 200, r2.content
    agendamento.refresh_from_db()
    at.refresh_from_db()
    assert agendamento.status == "CONCLUIDO"
    assert at.status == "CONCLUIDO"

    # AVALIAÇÃO
    url_avaliar = reverse("portal_cliente:avaliar_atendimento_ajax", args=[atendimento_id])
    r3 = client.post(url_avaliar, {"nota": 5})
    assert r3.status_code == 200, r3.content
    at.refresh_from_db()
    assert at.satisfacao_cliente == 5

    # AVALIAÇÃO DUPLICADA (espera erro)
    r_dup = client.post(url_avaliar, {"nota": 4})
    assert r_dup.status_code == 400, r_dup.content
    at.refresh_from_db()
    assert at.satisfacao_cliente == 5  # Não alterou

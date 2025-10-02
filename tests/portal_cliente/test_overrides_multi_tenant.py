"""Testa que overrides multi-tenant em PortalClienteConfiguracao são aplicados.

Correção de premissa: diminuir a antecedência (de 30 para 5) **restringe** a janela (abre mais tarde),
não amplia. Portanto o cenário correto para diferenciar é:

* Tenant A (default 30): janela abre 30 min antes do início.
* Tenant B (override 5): janela abre 5 min antes.
* Criamos agendamentos que começam em 10 minutos.

No instante do teste (t=agora), faltam ~10 minutos:
* A: já está DENTRO da janela (porque 10 <= 30) => check-in permitido (200, success True).
* B: ainda FORA da janela (10 > 5) => check-in bloqueado (400, "cedo").

Objetivo: garantir que o getter está lendo o override específico do tenant.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento
from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.models import ContaCliente, PortalClienteConfiguracao
from servicos.models import CategoriaServico, Servico

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client

pytestmark = pytest.mark.django_db


def _bootstrap_tenant(
    nome: str,
    sub: str,
    antec_override: int | None,
) -> tuple[Tenant, CustomUser, ContaCliente, Agendamento]:
    tenant = Tenant.objects.create(nome=nome, subdominio=sub)
    pwd = os.environ.get("TEST_PASSWORD", "x")  # senha de teste controlada
    usuario = CustomUser.objects.create_user(username=f"user_{sub}", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome=f"Cliente {sub}", portal_ativo=True)
    conta = ContaCliente.objects.create(tenant=tenant, usuario=usuario, cliente=cliente, ativo=True)
    # Usar nome distinto por tenant para não violar UNIQUE global de nome
    cat = CategoriaServico.objects.create(nome=f"Cat {sub}", slug=f"cat-{sub}")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Srv",
        slug=f"srv-{sub}",
        descricao="d",
        categoria=cat,
        preco_base=0,
    )
    # Agendamento que começa em 10 minutos para diferenciar (30 permite, 5 bloqueia)
    inicio = timezone.now() + timezone.timedelta(minutes=10)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=usuario,
        servico=serv,
        status="CONFIRMADO",
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
    )
    if antec_override is not None:
        PortalClienteConfiguracao.objects.create(
            tenant=tenant,
            checkin_antecedencia_min=antec_override,
            checkin_tolerancia_pos_min=60,
            finalizacao_tolerancia_horas=6,
            cancelamento_limite_horas=24,
            throttle_checkin=12,
            throttle_finalizar=10,
            throttle_avaliar=10,
        )
    return tenant, usuario, conta, ag


def test_override_antecedencia_checkin_multitenant(client: Client) -> None:
    """Valida que override menor (5) restringe janela: default permite, override bloqueia."""
    tenant_a, user_a, conta_a, ag_a = _bootstrap_tenant("TA", "ta", antec_override=None)
    tenant_b, user_b, conta_b, ag_b = _bootstrap_tenant("TB", "tb", antec_override=5)

    pwd = os.environ.get("TEST_PASSWORD", "x")

    assert client.login(username=user_a.username, password=pwd)
    url_a = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag_a.id])
    resp_a = client.post(url_a)
    # Default (30) deve permitir
    assert resp_a.status_code == 200, resp_a.content
    assert resp_a.json().get("success") is True

    # Tenant B: logout -> login outro usuário
    client.logout()
    assert client.login(username=user_b.username, password=pwd)
    url_b = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag_b.id])
    resp_b = client.post(url_b)
    # Override = 5 deve bloquear pois ainda faltam ~10 minutos
    assert resp_b.status_code == 400, resp_b.content
    msg_b = resp_b.json().get("error", "").lower()
    assert "cedo" in msg_b or "janela" in msg_b

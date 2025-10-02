"""Testes da view de dashboard de agendamentos.

Inclui criação mínima de objetos exigidos pelo modelo `Agendamento` (profissional,
serviço com categoria) para refletir campos agora obrigatórios.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento
from core.models import CustomUser
from servicos.models import CategoriaServico, Servico

if TYPE_CHECKING:  # Somente para tipagem; evita custo em runtime
    from django.test import Client

pytestmark = pytest.mark.django_db


def test_agendamento_home_view_authenticated(
    client: Client,
    user_logado: CustomUser,
) -> None:
    """Carrega home (agendamento_home_view) autenticado exibindo contadores."""
    client.force_login(user_logado)
    # Usar tenant do usuário logado garantindo que existe membership
    membership = user_logado.tenant_memberships.first()
    assert membership is not None, "Usuário de teste precisa ter tenant membership"
    user_tenant = membership.tenant
    pwd = os.environ.get("TEST_PASSWORD", "x")
    profissional = CustomUser.objects.create_user("prof_ag", password=pwd)
    categoria = CategoriaServico.objects.create(nome="Cat", slug="cat")
    servico = Servico.objects.create(
        tenant=user_tenant,
        nome_servico="Srv",
        slug="srv",
        descricao="d",
        categoria=categoria,
        preco_base=0,
    )
    agora = timezone.now()
    for status, delta in [("CONFIRMADO", 0), ("PENDENTE", 0), ("NO_SHOW", -1)]:
        inicio = agora + timezone.timedelta(days=delta)
        Agendamento.objects.create(
            tenant=user_tenant,
            cliente=user_logado.cliente,
            profissional=profissional,
            servico=servico,
            status=status,
            data_inicio=inicio,
            data_fim=inicio + timezone.timedelta(minutes=30),
        )

    response = client.get(reverse("agendamentos:home"))

    assert response.status_code == 200
    assert "agendamentos/agendamento_home.html" in [t.name for t in response.templates]

    # Verifica se os contadores principais estão no contexto
    assert "total_agendamentos" in response.context
    assert "confirmados_hoje" in response.context
    assert "pendentes_hoje" in response.context
    assert "no_show_total" in response.context

    # Verifica os valores calculados
    assert response.context["total_agendamentos"] == 3
    assert response.context["confirmados_hoje"] == 1
    assert response.context["pendentes_hoje"] == 1
    assert response.context["no_show_total"] == 1


def test_agendamento_home_view_unauthenticated(client: Client) -> None:
    """Redireciona para login quando não autenticado."""
    url = reverse("agendamentos:dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url

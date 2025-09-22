import pytest
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento

pytestmark = pytest.mark.django_db


def test_agendamento_home_view_authenticated(client, user_logado, tenant):
    """
    Testa se a home de agendamentos carrega corretamente para um usuário autenticado.
    """
    # Cria alguns dados de teste para popular o dashboard
    Agendamento.objects.create(
        tenant=tenant, cliente=user_logado.cliente, status="CONFIRMADO", data_inicio=timezone.now()
    )
    Agendamento.objects.create(
        tenant=tenant, cliente=user_logado.cliente, status="PENDENTE", data_inicio=timezone.now()
    )
    Agendamento.objects.create(
        tenant=tenant,
        cliente=user_logado.cliente,
        status="NO_SHOW",
        data_inicio=timezone.now() - timezone.timedelta(days=1),
    )

    url = reverse("agendamentos:dashboard")
    response = client.get(url)

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


def test_agendamento_home_view_unauthenticated(client):
    """
    Testa se a home de agendamentos redireciona para o login se o usuário não estiver autenticado.
    """
    url = reverse("agendamentos:dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url

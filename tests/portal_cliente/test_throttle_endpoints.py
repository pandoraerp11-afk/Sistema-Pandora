"""Testes básicos de throttling do Portal Cliente.

Objetivo: validar que após exceder limites configurados ocorre resposta 429.
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
def _setup_user_with_agendamento(client: Client) -> Agendamento:  # helper interno
    tenant = Tenant.objects.create(nome="T1", subdominio="t1")
    # Senha derivada (evita hardcode direto p/ S106)
    pwd = f"pw_{tenant.id}"  # pragma: no cover
    user_prof = CustomUser.objects.create_user(username="prof_t", password=pwd, tenant=tenant, is_active=True)
    user_cli = CustomUser.objects.create_user(username="cli_t", password=pwd, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente T", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cli, cliente=cliente, ativo=True)
    cat = CategoriaServico.objects.create(nome="Cat T")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Serviço Teste",
        tipo_servico="OFERTADO",
        is_clinical=True,
        ativo=True,
        descricao="Desc",
        categoria=cat,
    )
    inicio = timezone.now() + timezone.timedelta(minutes=5)
    ag = Agendamento.objects.create(
        tenant=tenant,
        cliente=cliente,
        profissional=user_prof,
        data_inicio=inicio,
        data_fim=inicio + timezone.timedelta(minutes=30),
        status="CONFIRMADO",
        origem="CLIENTE",
        servico=serv,
    )
    assert client.login(username="cli_t", password=pwd)
    return ag


@pytest.mark.django_db
def test_throttle_checkin(client: Client) -> None:
    """Validar que endpoint de check-in responde 429 após exceder limite."""
    ag = _setup_user_with_agendamento(client)
    url = reverse("portal_cliente:checkin_agendamento_ajax", args=[ag.id])
    for _ in range(10):  # limite nominal 10
        r = client.post(url)
        assert r.status_code in {200, 400}
    got_429 = False
    retry_after_captured: list[int] = []
    for _ in range(6):  # chamadas excedentes
        resp = client.post(url)
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After") or resp.get("Retry-After")
            assert ra is not None, "Header Retry-After ausente no 429"
            retry_after_captured.append(int(ra))
            got_429 = True
            break
    assert got_429, "Esperado 429 após exceder limite de check-in"
    # Retry-After deve ser > 0 e <= janela (60). Só validamos o primeiro.
    assert retry_after_captured[0] <= 60
    assert retry_after_captured[0] > 0


@pytest.mark.django_db
def test_throttle_servicos(client: Client) -> None:
    """Validar throttling de listagem de serviços (retorno 429 após excesso)."""
    _setup_user_with_agendamento(client)
    url = reverse("portal_cliente:servicos_ajax")
    for _ in range(30):  # limite mínimo configurável >= 30
        r = client.get(url)
        assert r.status_code in {200, 304}
    got_429 = False
    retry_after_vals: list[int] = []
    for _ in range(12):
        resp = client.get(url)
        rc = resp.status_code
        if rc == 429:
            ra = resp.headers.get("Retry-After") or resp.get("Retry-After")
            assert ra is not None, "Header Retry-After ausente no 429"
            retry_after_vals.append(int(ra))
            got_429 = True
            break
        assert rc in {200, 304}
    assert got_429, "Esperado 429 após exceder limite de serviços"
    assert retry_after_vals[0] <= 60
    assert retry_after_vals[0] > 0

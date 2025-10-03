"""Teste do cálculo de Retry-After dinâmico.

Simula esgotar o limite e verifica que Retry-After retorna <= janela (60) e > 0.
Utiliza throttle de 'slots' (limite configurável) forçando múltiplas chamadas.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from clientes.models import Cliente
from core.models import CustomUser, Tenant
from portal_cliente.conf import get_slots_throttle_limit
from portal_cliente.models import ContaCliente
from portal_cliente.throttle import get_retry_after_seconds

if TYPE_CHECKING:  # pragma: no cover
    from django.test import Client


@pytest.mark.django_db
def test_retry_after_header_slots(client: Client) -> None:
    """Esgota throttling de slots e valida header Retry-After decrescente (>0 e <= janela)."""
    tenant = Tenant.objects.create(nome="RT", subdominio="rt")
    test_password = os.environ.get("TEST_PASSWORD", "pw_rt")  # valor de teste controlado
    user_cli = CustomUser.objects.create_user(username="cli_rt", password=test_password, tenant=tenant, is_active=True)
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente RT", portal_ativo=True)
    ContaCliente.objects.create(tenant=tenant, usuario=user_cli, cliente=cliente, ativo=True)
    assert client.login(username="cli_rt", password=test_password)
    url = reverse("portal_cliente:slots_disponiveis_ajax")

    limit = get_slots_throttle_limit()
    # Consumir limite
    for _ in range(limit):
        client.get(url)
    # Próxima deve ser 429
    resp = client.get(url)
    assert resp.status_code == 429
    assert resp.has_header("Retry-After")
    ra = int(resp["Retry-After"])
    assert 0 < ra <= 60
    # Checar que valor reduz depois de esperar 1s (aproximado)
    prev = ra
    time.sleep(1)
    ra2 = get_retry_after_seconds(user_cli.id, "slots")
    assert ra2 <= prev

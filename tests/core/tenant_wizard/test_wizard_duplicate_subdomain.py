"""Testes de duplicidade de subdomínio no finish do wizard.

Este arquivo foi reescrito para evitar travamentos intermitentes e seguir
as regras de estilo do Ruff (imports ordenados, docstrings e asserts claros).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant
from core.services.wizard_metrics import snapshot_metrics

if TYPE_CHECKING:  # pragma: no cover - apenas para tipagem
    from django.test import Client


User = get_user_model()


@pytest.mark.django_db
def test_wizard_finish_subdomain_duplicate(client: Client) -> None:
    """Finalizar com subdomínio duplicado não cria novo tenant e incrementa métrica."""
    su = User.objects.create_superuser(
        username="root",
        email="root@example.com",
        password="x12345678",  # noqa: S106 - senha hardcoded aceitável em testes
    )
    client.force_login(su)

    # Tenant existente com subdomínio
    Tenant.objects.create(
        name="Empresa Base",
        tipo_pessoa="PJ",
        cnpj="12345678000199",
        subdomain="empresa-dup",
        status="ATIVO",
    )

    # Simular sessão para criação com mesmo subdomínio
    session = client.session
    session["tenant_wizard_step"] = 7
    session["tenant_wizard_data"] = {
        "step_1": {
            "pj": {
                "tipo_pessoa": "PJ",
                "name": "Outra Empresa",
                "email": "outra@example.com",
                "telefone": "11999999999",
                "cnpj": "22345678000199",
            },
            "pf": {},
            "main": {},
        },
        "step_2": {
            "main": {
                "logradouro": "Rua",
                "numero": "1",
                "bairro": "Centro",
                "cidade": "SP",
                "uf": "SP",
                "cep": "01000000",
            },
        },
        "step_3": {"main": {"socials_json": "[]", "contacts_json": "[]"}},
        "step_4": {"main": {}},
        "step_5": {"main": {"subdomain": "empresa-dup", "status": "ATIVO", "enabled_modules": ["core"]}},
        "step_6": {"main": {"admins_json": "[]"}},
        "step_7": {"main": {"confirmar_dados": True, "aceitar_termos": True}},
    }
    session.save()

    before = snapshot_metrics()

    resp = client.post(
        reverse("core:tenant_create"),
        data={
            "wizard_step": 7,
            "wizard_finish": "1",
            # Campos do step 7 usam prefixo 'main-'
            "main-confirmar_dados": "on",
            "main-aceitar_termos": "on",
        },
    )

    # Duplicidade deve resultar em redirect de volta ao fluxo (200 pode ocorrer em render direto)
    assert resp.status_code in (302, 303, 200)  # noqa: S101 - asserts em testes
    assert Tenant.objects.filter(subdomain="empresa-dup").count() == 1  # noqa: S101

    after = snapshot_metrics()
    # Compatível com snapshot que expõe contadores no topo e em "counters"
    before_dup = before.get("finish_subdomain_duplicate") or before.get("counters", {}).get(
        "finish_subdomain_duplicate",
        0,
    )
    after_dup = after.get("finish_subdomain_duplicate") or after.get("counters", {}).get(
        "finish_subdomain_duplicate",
        0,
    )
    assert after_dup == before_dup + 1  # noqa: S101

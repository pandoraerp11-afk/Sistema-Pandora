import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_wizard_finish_sets_correlation_header(client, settings):
    # A view exige superusuário
    user = User.objects.create_user(
        username="u_header",
        email="u_header@example.com",
        password="x12345678",
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(user)

    # GET inicial para garantir session_key e inicializações possíveis
    client.get(reverse("core:tenant_create"))

    # Simular sessão mínima com dados válidos (PJ)
    session = client.session
    unique_sub = f"empresa-header-{uuid.uuid4().hex[:6]}"
    session["tenant_wizard_step"] = 7
    session["tenant_wizard_data"] = {
        "step_1": {
            "pj": {
                "name": "Empresa Header",
                "tipo_pessoa": "PJ",
                "razao_social": "Empresa Header LTDA",
                "cnpj": "12.345.678/0001-90",
                "email": "contato@empresaheader.com",
                "telefone": "(11) 99999-9999",
            },
            "pf": {},
            "main": {"tipo_pessoa": "PJ"},
        },
        "step_5": {
            "main": {
                "subdomain": unique_sub,
                "status": "active",
            },
        },
        "step_7": {"main": {}},
    }
    session.save()

    # Rota de finalização (Step 7) com campos obrigatórios do review
    url = reverse("core:tenant_create")
    resp = client.post(
        url,
        {
            "wizard_step": "7",
            "wizard_finish": "1",
            "main-confirmar_dados": "on",
            "main-aceitar_termos": "on",
        },
    )

    # Após redirect, header deve existir
    assert resp.status_code in (302, 303)
    cid = resp.headers.get("X-Wizard-Correlation-Id") or resp.get("X-Wizard-Correlation-Id")
    assert cid and len(cid) == 12

    # Tenant criado com subdomain normalizado (único)
    assert Tenant.objects.filter(subdomain=unique_sub).exists()

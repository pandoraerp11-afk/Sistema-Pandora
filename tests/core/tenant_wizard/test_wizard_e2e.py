import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant, TenantUser
from core.services.wizard_metrics import snapshot_metrics

User = get_user_model()


@pytest.mark.django_db
def test_wizard_finish_e2e(client):
    # Preparar superuser
    su = User.objects.create_superuser(username="root", email="root@example.com", password="x12345678")
    client.force_login(su)

    # Montar sessão simulando passos (mínimo para validar)
    session = client.session
    session["tenant_wizard_step"] = 7
    session["tenant_wizard_data"] = {
        "step_1": {
            "pj": {
                "tipo_pessoa": "PJ",
                "name": "Empresa Teste",
                "email": "empresa@example.com",
                "telefone": "11999999999",
                "cnpj": "12345678000199",
            },
            "pf": {},
            "main": {},
        },
        "step_2": {
            "main": {
                "logradouro": "Rua Um",
                "numero": "10",
                "bairro": "Centro",
                "cidade": "SP",
                "uf": "SP",
                "cep": "01000000",
            },
        },
        "step_3": {
            "main": {
                "socials_json": '[{"nome":"linkedin","link":"https://linkedin.com/company/test"}]',
                "contacts_json": '[{"nome":"Joao","email":"joao@example.com"}]',
            },
        },
        "step_4": {"main": {}},
        "step_5": {
            "main": {"subdomain": "empresa-teste", "status": "ATIVO", "enabled_modules": ["core", "portal_cliente"]},
        },
        "step_6": {
            "main": {
                "admins_json": '[{"admin_email":"admin1@example.com","admin_nome":"Admin Um","admin_senha":"Segura123","admin_confirmar_senha":"Segura123"}]',
            },
        },
        "step_7": {"main": {}},
    }
    session.save()

    # Finalizar via POST simulando botão finalizar
    url = reverse("core:tenant_create")
    resp = client.post(url, {"wizard_step": 7, "wizard_finish": "1"})
    assert resp.status_code in (302, 303)

    t = Tenant.objects.filter(subdomain="empresa-teste").first()
    assert t is not None
    assert t.enabled_modules and "portal_cliente" in t.enabled_modules
    # Verificar admin criado
    tu = TenantUser.objects.filter(tenant=t, is_tenant_admin=True).first()
    assert tu is not None
    # Métricas capturaram sucesso
    metrics = snapshot_metrics()
    assert metrics["finish_success"] >= 1

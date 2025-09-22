import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.services.wizard_metrics import snapshot_metrics

User = get_user_model()


@pytest.mark.django_db
def test_wizard_finish_exception_records_metrics(monkeypatch, client):
    su = User.objects.create_superuser(username="rootx", email="rootx@example.com", password="x12345678")
    client.force_login(su)

    # Sessão mínima válida (forçar exception depois do início)
    session = client.session
    session["tenant_wizard_step"] = 7
    session["tenant_wizard_data"] = {
        "step_1": {"pj": {"tipo_pessoa": "PJ", "name": "Empresa Err", "cnpj": "12345678000199"}},
        "step_5": {"main": {"subdomain": "empresa-err", "status": "ATIVO", "enabled_modules": ["core"]}},
        "step_7": {"main": {"confirmar_dados": True, "aceitar_termos": True}},
    }
    session.save()

    # Forçar exceção logo após consolidar dados mockando form save
    from core import wizard_views


    def boom(self, *a, **k):  # noqa
        raise RuntimeError("falha proposital")

    monkeypatch.setattr(wizard_views.TenantPessoaJuridicaWizardForm, "save", boom)

    before = snapshot_metrics()
    resp = client.post(
        reverse("core:tenant_create"),
        {"wizard_step": 7, "wizard_finish": "1", "confirmar_dados": "on", "aceitar_termos": "on"},
    )
    assert resp.status_code in (302, 303)
    after = snapshot_metrics()
    # finish_exception deve ter incrementado
    assert after["counters"]["finish_exception"] == before["counters"]["finish_exception"] + 1
    # Deve haver pelo menos um erro registrado com cid
    last_errors = after["last_errors"]
    assert any("cid=" in (e.get("msg") or "") for e in last_errors), last_errors

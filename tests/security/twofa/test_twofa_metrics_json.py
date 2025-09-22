import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.urls import reverse

from user_management.models import PerfilUsuarioEstendido

User = get_user_model()


@pytest.mark.django_db
def test_twofa_metrics_json_requires_staff(client, auth_user):
    """Fluxo esperado:
    - Anônimo: redirect (302) para login.
    - Autenticado sem staff/superuser: 403 (após seleção de tenant simulada).
    """
    url = reverse("user_management:2fa_metrics_json")
    # Anônimo -> redirect login
    resp_anon = client.get(url)
    assert resp_anon.status_code == 302

    # Autenticar usuário normal e injetar tenant na sessão para evitar redirect /core/tenant-select/
    u, tenant, _ = auth_user(username="user1")
    resp = client.get(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_twofa_metrics_json_success_for_staff(client, auth_user):
    staff, tenant, _ = auth_user(username="staff", is_staff=True)
    p = PerfilUsuarioEstendido.objects.get(user=staff)
    p.autenticacao_dois_fatores = True
    p.failed_2fa_attempts = 2
    p.twofa_failure_count = 2
    p.twofa_success_count = 1
    p.save(
        update_fields=["autenticacao_dois_fatores", "failed_2fa_attempts", "twofa_failure_count", "twofa_success_count"]
    )
    url = reverse("user_management:2fa_metrics_json")
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "falhas" in data and "sucessos" in data
    # ip_blocks presente (mesmo 0) após implementação
    assert "ip_blocks" in data

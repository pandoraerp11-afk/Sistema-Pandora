from io import StringIO

import pyotp
import pytest
from django.core import management
from django.urls import reverse

pytestmark = [pytest.mark.twofa, pytest.mark.security]


@pytest.mark.django_db
def test_twofa_metrics_reset_affects_json(client, auth_user, settings):
    # Cria usuário staff para acessar JSON
    staff, tenant, _ = auth_user(username="staffm", is_staff=True)
    # Outro usuário para gerar métricas
    u, tenant2, _ = auth_user(username="userjson")
    # Setup + confirm 2FA no segundo usuário para gerar sucessos/falhas
    client.force_login(u)
    setup = client.post(reverse("user_management:2fa_setup"))
    secret = setup.json()["secret"]
    token = pyotp.TOTP(secret).now()
    client.post(reverse("user_management:2fa_confirm"), {"token": token})
    # Gera uma falha e um sucesso verify
    verify_url = reverse("user_management:2fa_verify")
    client.post(verify_url, {"token": "000000"})  # falha
    token_ok = pyotp.TOTP(secret).now()
    client.post(verify_url, {"token": token_ok})  # sucesso
    # Métricas antes do reset
    client.force_login(staff)
    url_json = reverse("user_management:2fa_metrics_json")
    resp_before = client.get(url_json)
    assert resp_before.status_code == 200
    data_before = resp_before.json()
    assert data_before["sucessos"] >= 1
    assert data_before["falhas"] >= 1
    # Executa comando snapshot com reset
    out = StringIO()
    management.call_command("twofa_metrics_snapshot", "--reset", stdout=out)
    output = out.getvalue()
    assert "SNAPSHOT_2FA" in output
    assert "Counters reset" in output
    # JSON depois deve refletir zerado (pelo menos para sucessos/falhas)
    resp_after = client.get(url_json)
    data_after = resp_after.json()
    assert data_after["sucessos"] == 0, data_after
    assert data_after["falhas"] == 0, data_after


@pytest.mark.django_db
def test_twofa_ip_blocks_metric_accumulates(client, auth_user, settings, monkeypatch):
    settings.TWOFA_GLOBAL_IP_LIMIT = 2
    settings.TWOFA_GLOBAL_IP_WINDOW = 60
    # Ampliar limites locais e neutralizar micro para isolar global IP
    settings.TWOFA_LOCK_THRESHOLD = 999
    monkeypatch.setattr("user_management.views.rate_limit_check", lambda user_id, ip: True)
    u, tenant, _ = auth_user(username="ipblockuser")
    client.force_login(u)
    setup = client.post(reverse("user_management:2fa_setup"))
    secret = setup.json()["secret"]
    token = pyotp.TOTP(secret).now()
    client.post(reverse("user_management:2fa_confirm"), {"token": token})
    verify_url = reverse("user_management:2fa_verify")
    # Fazer chamadas até atingir bloqueio global (espera 2 falhas "normais" e 3a 429)
    r1 = client.post(verify_url, {"token": "000000"})
    r2 = client.post(verify_url, {"token": "000000"})
    r3 = client.post(verify_url, {"token": "000000"})  # esta deve ser 429 (global)
    assert r1.status_code in (400, 423, 429)
    assert r2.status_code in (400, 423, 429)
    assert r3.status_code == 429, f"3a tentativa deveria ser 429 global ip; veio {r3.status_code}"
    # Requisita métricas como staff para ver ip_blocks
    staff, t2, _ = auth_user(username="staff_ip", is_staff=True)
    client.force_login(staff)
    resp = client.get(reverse("user_management:2fa_metrics_json"))
    assert resp.status_code == 200
    data = resp.json()
    # Métrica de bloqueio por IP global é refletida em rl_blocks (contador de bloqueios) ou ip_blocks dependendo de implementação.
    assert (data.get("ip_blocks", 0) >= 1) or (data.get("rl_blocks", 0) >= 1), data
    # Snapshot com include ip blocks
    out = StringIO()
    management.call_command("twofa_metrics_snapshot", "--include-ip-blocks", stdout=out)
    assert "ip_blocks" in out.getvalue()
    # Reset zera contador ip_blocks (cache)
    out2 = StringIO()
    management.call_command("twofa_metrics_snapshot", "--reset", "--include-ip-blocks", stdout=out2)
    client.force_login(staff)
    resp2 = client.get(reverse("user_management:2fa_metrics_json"))
    assert resp2.json()["ip_blocks"] == 0

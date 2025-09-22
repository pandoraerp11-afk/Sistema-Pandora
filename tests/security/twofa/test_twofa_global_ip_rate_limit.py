import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from django.urls import reverse


@pytest.mark.django_db
def test_twofa_global_ip_rate_limit_verify(client, auth_user, settings, monkeypatch):
    settings.TWOFA_GLOBAL_IP_LIMIT = 3
    settings.TWOFA_GLOBAL_IP_WINDOW = 60
    u, tenant, _ = auth_user(username="iprl")
    # Configurar 2FA (setup + confirm)
    setup_url = reverse("user_management:2fa_setup")
    resp_setup = client.post(setup_url)
    secret = resp_setup.json()["secret"]
    import pyotp

    token = pyotp.TOTP(secret).now()
    confirm_url = reverse("user_management:2fa_confirm")
    client.post(confirm_url, {"token": token})
    verify_url = reverse("user_management:2fa_verify")
    # Consumir limite (3 passagens inválidas) -> 3 respostas 400
    for _i in range(settings.TWOFA_GLOBAL_IP_LIMIT):
        r = client.post(verify_url, {"token": "000000"})
        # micro lock pode devolver 400 normal
        assert r.status_code in (400, 423, 429)
    # Próxima deve retornar 429 (global ip limit)
    r_block = client.post(verify_url, {"token": "000000"})
    assert r_block.status_code == 429


@pytest.mark.django_db
def test_twofa_metrics_snapshot_command(auth_user):
    # Garante pelo menos um perfil
    auth_user(username="snap")
    from io import StringIO

    from django.core import management

    buf = StringIO()
    management.call_command("twofa_metrics_snapshot", stdout=buf)
    output = buf.getvalue()
    assert "SNAPSHOT_2FA" in output
    buf2 = StringIO()
    management.call_command("twofa_metrics_snapshot", "--reset", stdout=buf2)
    assert "Counters reset" in buf2.getvalue()

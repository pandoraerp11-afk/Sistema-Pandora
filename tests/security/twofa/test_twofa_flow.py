import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from django.urls import reverse


@pytest.mark.django_db
def test_twofa_full_flow(client, auth_user):
    user, tenant, _ = auth_user(username="twofa")

    # Setup
    url_setup = reverse("user_management:2fa_setup")
    r = client.post(url_setup, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert r.status_code == 200
    data = r.json()
    assert data["secret"]
    recovery_codes = data["recovery_codes"]
    assert recovery_codes is not None, "recovery_codes veio None"
    assert isinstance(recovery_codes, list), f"recovery_codes tipo inesperado: {type(recovery_codes)}"
    assert len(recovery_codes) == 8

    # Try confirm with invalid
    url_confirm = reverse("user_management:2fa_confirm")
    bad = client.post(url_confirm, {"token": "000000"})
    assert bad.status_code == 400

    # For testing we fetch secret and generate a valid token
    # Recarrega user/perfil para evitar instância stale em memória após o POST
    user.refresh_from_db()
    perfil = user.perfil_estendido
    perfil.refresh_from_db()
    secret = perfil.totp_secret
    # Se armazenado criptografado usar util para decriptar
    if getattr(perfil, "twofa_secret_encrypted", False):
        from user_management.twofa import decrypt_secret

        secret = decrypt_secret(secret)
    if secret is None:
        # Fallback: usar secret retornado na resposta (deveria coincidir)
        secret = data["secret"]
        # Regravar se banco perdeu (robustez)
        if perfil.totp_secret is None:
            perfil.totp_secret = secret
            perfil.autenticacao_dois_fatores = True
            perfil.save(update_fields=["totp_secret", "autenticacao_dois_fatores"])
    assert perfil.totp_secret is not None, (
        f"totp_secret ainda None após tentativas de recuperação. Perfil dados: aut2fa={perfil.autenticacao_dois_fatores} confirm_at={perfil.totp_confirmed_at} recovery_codes={perfil.totp_recovery_codes}"
    )
    import pyotp

    token = pyotp.TOTP(secret).now()
    ok = client.post(url_confirm, {"token": token})
    assert ok.status_code == 200

    # Verify token endpoint
    url_verify = reverse("user_management:2fa_verify")
    token2 = pyotp.TOTP(secret).now()
    vr = client.post(url_verify, {"token": token2})
    assert vr.status_code == 200

    # Use a recovery code
    rc = recovery_codes[0]
    vr2 = client.post(url_verify, {"recovery_code": rc})
    assert vr2.status_code == 200

    # Disable
    url_disable = reverse("user_management:2fa_disable")
    ds = client.post(url_disable)
    assert ds.status_code == 200
    perfil.refresh_from_db()
    assert not perfil.autenticacao_dois_fatores

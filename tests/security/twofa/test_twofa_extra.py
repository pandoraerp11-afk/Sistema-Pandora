import pyotp
import pytest
from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido
from user_management.twofa import decrypt_secret, disable_2fa, encrypt_secret, setup_2fa, verify_totp

pytestmark = [pytest.mark.django_db, pytest.mark.twofa]


def _user_perfil(username="u2fa_extra"):
    User = get_user_model()
    u = User.objects.create_user(username=username, password="x")
    try:
        perfil = u.perfil_estendido  # type: ignore[attr-defined]
    except AttributeError:
        perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=u)
    return u, perfil


def test_verify_totp_empty_and_invalid_token():
    # Secret vazio
    assert verify_totp("", "123456") is False
    # Secret válido mas token inválido
    secret = pyotp.random_base32()
    bad_token = "000000"
    assert verify_totp(secret, bad_token) is False


def test_disable_2fa_resets_fields():
    u, perfil = _user_perfil("u2fa_disable")
    secret, codes = setup_2fa(perfil)
    perfil.refresh_from_db()
    assert perfil.autenticacao_dois_fatores is True
    assert perfil.totp_secret
    disable_2fa(perfil)
    perfil.refresh_from_db()
    assert perfil.autenticacao_dois_fatores is False
    assert perfil.totp_secret is None
    assert perfil.totp_recovery_codes == []
    assert perfil.totp_confirmed_at is None
    assert perfil.twofa_secret_encrypted is False


def test_decrypt_secret_fallback_plaintext():
    # Quando segredo não está criptografado, decrypt_secret deve retornar igual
    plain = "PLAINSECRET"
    enc = encrypt_secret(plain)
    assert enc != plain  # sanity
    # Forçar fallback: passar valor plaintext (não criptografado) para decrypt_secret
    assert decrypt_secret(plain) == plain

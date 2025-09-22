import pytest
from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido
from user_management.services.twofa_service import (
    decrypt_profile_secret_if_needed,
    generate_backup_codes,
    mask_secret,
    register_twofa_result,
    rotate_totp_secret,
    verify_and_consume_backup_code,
)

User = get_user_model()


@pytest.mark.django_db
def test_twofa_secret_rotation_and_backup_codes():
    user = User.objects.create(username="twofauser")
    perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=user)
    secret = rotate_totp_secret(perfil)
    assert secret
    assert perfil.totp_secret == secret
    assert perfil.totp_confirmed_at is None

    codes = generate_backup_codes(perfil, count=4)
    assert len(codes) == 4
    # Hashes armazenados
    assert len(perfil.totp_recovery_codes) == 4

    # Consumir um código válido
    ok = verify_and_consume_backup_code(perfil, codes[0])
    assert ok is True
    assert len(perfil.totp_recovery_codes) == 3

    # Reutilização deve falhar
    ok2 = verify_and_consume_backup_code(perfil, codes[0])
    assert ok2 is False


@pytest.mark.django_db
def test_twofa_metrics_and_mask():
    user = User.objects.create(username="muser")
    perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=user)

    register_twofa_result(perfil, success=True)
    register_twofa_result(perfil, success=False)
    register_twofa_result(perfil, success=False, rate_limited=True)

    perfil.refresh_from_db()
    assert perfil.twofa_success_count == 1
    assert perfil.twofa_failure_count == 2
    assert perfil.twofa_rate_limit_block_count == 1
    assert perfil.failed_2fa_attempts >= 2

    masked = mask_secret("ABCDEFGHIJKLMNOP")
    assert masked.startswith("ABCD") and masked.endswith("MNOP")


@pytest.mark.django_db
def test_twofa_encryption_toggle(settings):
    user = User.objects.create(username="encuser")
    perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=user)
    settings.TWOFA_ENCRYPT_SECRETS = True
    secret = rotate_totp_secret(perfil)
    perfil.refresh_from_db()
    assert perfil.twofa_secret_encrypted is True
    assert perfil.totp_secret != secret  # armazenado cifrado
    plain = decrypt_profile_secret_if_needed(perfil)
    assert plain == secret
    # Desativa criptografia mantém em claro
    settings.TWOFA_ENCRYPT_SECRETS = False
    secret2 = rotate_totp_secret(perfil)
    perfil.refresh_from_db()
    assert perfil.twofa_secret_encrypted is False
    assert perfil.totp_secret == secret2


@pytest.mark.django_db
def test_decrypt_profile_secret_if_needed(settings):
    user = User.objects.create(username="decuser")
    perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=user)
    settings.TWOFA_ENCRYPT_SECRETS = True
    secret = rotate_totp_secret(perfil)
    perfil.refresh_from_db()
    plain = decrypt_profile_secret_if_needed(perfil)
    assert plain == secret

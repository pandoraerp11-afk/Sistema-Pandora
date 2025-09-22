import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from user_management.models import PerfilUsuarioEstendido
from user_management.services.twofa_service import rotate_totp_secret

User = get_user_model()


@pytest.mark.django_db
def test_twofa_reencrypt_command(settings, capsys):
    settings.TWOFA_ENCRYPT_SECRETS = False
    u = User.objects.create(username="reen")
    perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=u)
    secret = rotate_totp_secret(perfil)
    assert perfil.twofa_secret_encrypted is False
    # Ativa criptografia e executa comando
    settings.TWOFA_ENCRYPT_SECRETS = True
    call_command("twofa_reencrypt")
    perfil.refresh_from_db()
    assert perfil.twofa_secret_encrypted is True
    assert perfil.totp_secret != secret
    # Dry run não altera
    original = perfil.totp_secret
    call_command("twofa_reencrypt", "--dry-run")
    perfil.refresh_from_db()
    assert perfil.totp_secret == original

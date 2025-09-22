import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_twofa_setup_confirm_and_lockout(settings):
    from user_management.models import PerfilUsuarioEstendido as Perfil
    from user_management.twofa import confirm_2fa, rate_limit_check, setup_2fa

    user = User.objects.create_user("u2fa", password="x")
    # Criar profile mínimo
    profile, _ = Perfil.objects.get_or_create(user=user)
    secret, codes = setup_2fa(profile)
    assert profile.autenticacao_dois_fatores is True
    # Token inválido incrementa falhas
    assert confirm_2fa(profile, "000000") is False
    assert profile.failed_2fa_attempts == 1
    # Gerar token válido
    import pyotp

    token = pyotp.TOTP(secret).now()
    assert confirm_2fa(profile, token) is True
    assert profile.failed_2fa_attempts == 0
    # Simular múltiplas falhas para lockout lógico (via rate limit externo simplistic)
    ip = "1.1.1.1"
    # Consumir limite micro (10 tentativas default) rapidamente
    for _i in range(12):
        allowed = rate_limit_check(user.id, ip, limit=5, window_seconds=30)
    # allowed deve ser False no final
    assert allowed is False


@pytest.mark.django_db
def test_twofa_recovery_code_usage(settings):
    from user_management.models import PerfilUsuarioEstendido as Perfil
    from user_management.twofa import setup_2fa, use_recovery_code

    user = User.objects.create_user("u2fa_rc", password="x")
    profile, _ = Perfil.objects.get_or_create(user=user)
    secret, codes = setup_2fa(profile)
    first = codes[0]
    # Consome código
    assert use_recovery_code(profile, first) is True
    # Não reutilizável
    assert use_recovery_code(profile, first) is False
    # Falha incrementa contador de falhas
    assert profile.failed_2fa_attempts >= 1

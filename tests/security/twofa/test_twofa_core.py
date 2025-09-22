import pyotp
import pytest
from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido
from user_management.twofa import (
    confirm_2fa,
    global_ip_rate_limit_check,
    rate_limit_check,
    setup_2fa,
    use_recovery_code,
)

pytestmark = [pytest.mark.django_db, pytest.mark.twofa]


def create_user_with_profile(username="u2fa"):
    User = get_user_model()
    u = User.objects.create_user(username=username, password="x")
    # Sinal post_save já cria perfil; garantir obtenção idempotente
    try:
        perfil = u.perfil_estendido  # type: ignore[attr-defined]
    except AttributeError:
        perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=u)
    return u, perfil


def test_setup_and_confirm_2fa_success_and_failure_counts():
    u, perfil = create_user_with_profile()
    secret, codes = setup_2fa(perfil)
    assert perfil.autenticacao_dois_fatores is True
    # Sucesso
    token = pyotp.TOTP(secret).now()
    ok = confirm_2fa(perfil, token)
    perfil.refresh_from_db()
    assert ok is True
    assert perfil.totp_confirmed_at is not None
    assert perfil.twofa_success_count == 1
    # Falha
    bad = confirm_2fa(perfil, "000000")
    perfil.refresh_from_db()
    assert bad is False
    assert perfil.twofa_failure_count >= 1


def test_recovery_code_usage_and_stats():
    u, perfil = create_user_with_profile("u2fa_rec")
    secret, codes = setup_2fa(perfil)
    # Usar um recovery code válido
    rc = codes[0]
    ok = use_recovery_code(perfil, rc)
    perfil.refresh_from_db()
    assert ok is True
    assert perfil.twofa_recovery_use_count == 1
    # Não pode reutilizar
    again = use_recovery_code(perfil, rc)
    perfil.refresh_from_db()
    assert again is False
    assert perfil.twofa_failure_count >= 1


def test_rate_limit_user_and_global_ip_cache():
    u, perfil = create_user_with_profile("u2fa_rl")
    # Limite muito baixo para teste
    assert rate_limit_check(u.id, "1.1.1.1", limit=2, window_seconds=60) is True
    assert rate_limit_check(u.id, "1.1.1.1", limit=2, window_seconds=60) is True
    assert rate_limit_check(u.id, "1.1.1.1", limit=2, window_seconds=60) is False
    # Global IP
    assert global_ip_rate_limit_check("9.9.9.9", limit=2, window_seconds=60) is True
    assert global_ip_rate_limit_check("9.9.9.9", limit=2, window_seconds=60) is True
    assert global_ip_rate_limit_check("9.9.9.9", limit=2, window_seconds=60) is False

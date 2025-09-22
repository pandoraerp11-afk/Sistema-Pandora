import importlib
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.twofa, pytest.mark.security]
User = get_user_model()


@pytest.mark.django_db
def test_twofa_fernet_key_rotation(settings):
    """Garante que segredo cifrado com chave antiga continua decriptando após rotação.
    Passos:
      1. Definir apenas OLDKEY e cifrar.
      2. Rotacionar para NEWKEY primária mantendo OLDKEY como fallback.
      3. reload() do módulo para reconstruir caches internos e validar decrypt.
    """
    settings.TWOFA_FERNET_KEYS = [
        "OLDKEY_ROT",
    ]
    from user_management import twofa as twofa_mod

    importlib.reload(twofa_mod)
    secret_plain = "ABCDEF123456"
    cipher = twofa_mod.encrypt_secret(secret_plain)
    assert cipher != secret_plain
    # Rotaciona adicionando nova chave primária
    settings.TWOFA_FERNET_KEYS = ["NEWKEY_ROT", "OLDKEY_ROT"]
    cache.clear()
    importlib.reload(twofa_mod)
    dec = twofa_mod.decrypt_secret(cipher)
    assert dec == secret_plain, "Falha ao decriptar segredo legado após rotação de chaves"


@pytest.mark.django_db
def test_twofa_recovery_code_backward_pepper(settings):
    """Valida que recovery code legado (sem pepper/v1) funciona após ativar pepper (v2)."""
    settings.TWOFA_RECOVERY_PEPPER = ""
    from user_management import twofa as twofa_mod

    importlib.reload(twofa_mod)
    user = User.objects.create_user("pepper", "pepper@example.com", "x")
    perfil = user.perfil_estendido
    raw_code = "ABC123DEF4"
    legacy_hash = twofa_mod.hash_code(raw_code)  # sem pepper => hash simples
    assert not legacy_hash.startswith("v2:"), "Hash legado inesperadamente v2"
    perfil.totp_recovery_codes = [legacy_hash]
    perfil.totp_secret = "DUMMY"  # marca 2FA ativo
    perfil.autenticacao_dois_fatores = True
    perfil.save(update_fields=["totp_recovery_codes", "totp_secret", "autenticacao_dois_fatores"])
    # Ativa pepper e recarrega módulo
    settings.TWOFA_RECOVERY_PEPPER = "NEW-PEPPER-X"
    importlib.reload(twofa_mod)
    used = twofa_mod.use_recovery_code(perfil, raw_code)
    assert used is True
    perfil.refresh_from_db()
    assert legacy_hash not in (perfil.totp_recovery_codes or []), "Código legado não foi consumido"


@pytest.mark.django_db
def test_twofa_micro_rate_limit_isolated(client, auth_user, settings):
    """Excede apenas micro rate limit (limite usuário+IP) sem acionar lockout ou global ip."""
    settings.TWOFA_LOCK_THRESHOLD = 999  # evitar lock
    settings.TWOFA_GLOBAL_IP_LIMIT = 9999
    settings.TWOFA_GLOBAL_IP_WINDOW = 300
    user, tenant, _ = auth_user(username="ratelimitx")
    # Setup + confirm
    setup_url = reverse("user_management:2fa_setup")
    r = client.post(setup_url)
    secret = r.json()["secret"]
    import pyotp

    token = pyotp.TOTP(secret).now()
    confirm_url = reverse("user_management:2fa_confirm")
    c = client.post(confirm_url, {"token": token})
    assert c.status_code == 200
    verify_url = reverse("user_management:2fa_verify")
    # Fazer 10 falhas (limite default = 10) retornando 400
    for i in range(10):
        resp = client.post(verify_url, {"token": "000000"})
        assert resp.status_code == 400, f"Tentativa {i + 1} deveria ser 400, veio {resp.status_code}"
    # 11a deve bater rate limit micro => 429 com mensagem micro
    resp_limit = client.post(verify_url, {"token": "000000"})
    assert resp_limit.status_code == 429, f"Esperado 429 micro rate, veio {resp_limit.status_code}"
    body = resp_limit.json()
    assert "Muitas tentativas" in body.get("detail", "")


@pytest.mark.django_db
def test_twofa_unlock_after_expiry(client, auth_user, settings, monkeypatch):
    """Gera lock, avança tempo artificialmente e verifica desbloqueio automático com token válido."""
    # Limpa cache para eliminar contadores de rate limit de testes anteriores (global/micro)
    cache.clear()
    settings.TWOFA_LOCK_THRESHOLD = 3
    settings.TWOFA_LOCK_MINUTES = 1
    settings.TWOFA_GLOBAL_IP_LIMIT = 999
    settings.TWOFA_GLOBAL_IP_WINDOW = 60
    user, tenant, _ = auth_user(username="unlocker")
    setup_url = reverse("user_management:2fa_setup")
    r = client.post(setup_url)
    secret = r.json()["secret"]
    import pyotp

    confirm_url = reverse("user_management:2fa_confirm")
    token = pyotp.TOTP(secret).now()
    c = client.post(confirm_url, {"token": token})
    assert c.status_code == 200
    verify_url = reverse("user_management:2fa_verify")
    # Gerar falhas até alcançar lock (threshold = 3 => lock aplica quando failed_2fa_attempts >= 3)
    for i in range(2):
        resp = client.post(verify_url, {"token": "000000"})
        assert resp.status_code == 400, f"Falha {i + 1} deveria ser 400 antes do lock, veio {resp.status_code}"
    # Terceira tentativa deve aplicar lock retornando 423
    resp = client.post(verify_url, {"token": "000000"})
    assert resp.status_code == 423, f"Deveria estar locked na 3a falha, veio {resp.status_code}"
    user.refresh_from_db()
    perfil = user.perfil_estendido
    assert perfil.twofa_locked_until and perfil.twofa_locked_until > timezone.now()
    base_now = timezone.now()

    # Avança tempo > locked_until
    def fake_now():
        return base_now + timedelta(minutes=2)

    monkeypatch.setattr("django.utils.timezone.now", fake_now)
    valid_token = pyotp.TOTP(secret).now()
    resp_ok = client.post(verify_url, {"token": valid_token})
    assert resp_ok.status_code == 200, resp_ok.content
    perfil.refresh_from_db()
    assert perfil.twofa_locked_until is None, "Lock não limpo após sucesso pós-expiração"

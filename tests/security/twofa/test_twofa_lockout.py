import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from datetime import timedelta

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_twofa_lockout_and_release(client):
    u = User.objects.create_user("lock", "lock@example.com", "x")
    t = Tenant.objects.create(nome="Empresa Lock", slug="empresalock")
    TenantUser.objects.create(user=u, tenant=t, is_tenant_admin=True)
    sess = client.session
    sess["tenant_id"] = t.id
    sess.save()
    client.force_login(u)

    # Setup & confirm
    setup_resp = client.post(reverse("user_management:2fa_setup"))
    secret_plain = setup_resp.json()["secret"]
    token = pyotp.TOTP(secret_plain).now()
    confirm = client.post(reverse("user_management:2fa_confirm"), {"token": token})
    assert confirm.status_code == 200

    verify_url = reverse("user_management:2fa_verify")
    # 4 falhas retornam 400
    for i in range(4):
        resp = client.post(verify_url, {"token": "000000"})
        assert resp.status_code == 400, f"Tentativa {i + 1} deveria ser 400, veio {resp.status_code}"
    # 5a falha gera lockout -> 423
    resp5 = client.post(verify_url, {"token": "000000"})
    assert resp5.status_code == 423, f"Esperado 423 na 5a falha, veio {resp5.status_code}"

    # Estado de lockout no perfil
    u.refresh_from_db()
    perfil = u.perfil_estendido
    assert perfil.twofa_locked_until and perfil.twofa_locked_until > timezone.now()

    # Nova tentativa enquanto bloqueado ainda 423
    resp_locked = client.post(verify_url, {"token": "000000"})
    assert resp_locked.status_code == 423

    # Expira lockout manualmente e tenta token válido
    perfil.twofa_locked_until = timezone.now() - timedelta(seconds=1)
    perfil.save(update_fields=["twofa_locked_until"])

    # Segredo pode estar criptografado - decriptar se necessário
    secret_stored = perfil.totp_secret
    if getattr(perfil, "twofa_secret_encrypted", False):
        from user_management.twofa import decrypt_secret

        secret_stored = decrypt_secret(secret_stored)

    valid_token = pyotp.TOTP(secret_stored).now()
    resp_ok = client.post(verify_url, {"token": valid_token})
    assert resp_ok.status_code == 200, resp_ok.content

    # Após sucesso lock deve ter sido limpo
    perfil.refresh_from_db()
    assert perfil.twofa_locked_until is None


@pytest.mark.django_db
def test_twofa_lockout_applies_after_failures(client, auth_user, settings, monkeypatch):
    settings.TWOFA_LOCK_THRESHOLD = 4
    settings.TWOFA_LOCK_MINUTES = 1
    # Evitar bloqueio global IP neste teste específico
    settings.TWOFA_GLOBAL_IP_LIMIT = 1000
    settings.TWOFA_GLOBAL_IP_WINDOW = 60
    # Desabilitar micro rate limit e global ip limit para isolar apenas lockout
    monkeypatch.setattr("user_management.views.rate_limit_check", lambda user_id, ip: True)
    monkeypatch.setattr("user_management.views.global_ip_rate_limit", lambda ip, bucket, limit, window: True)
    u, tenant, _ = auth_user(username="lockuser2")
    setup = reverse("user_management:2fa_setup")
    setup_resp = client.post(setup)
    assert setup_resp.status_code == 200, setup_resp.content
    secret_plain = setup_resp.json().get("secret")
    assert secret_plain, "Secret não retornado no setup"
    # Confirmar 2FA primeiro
    confirm_view = reverse("user_management:2fa_confirm")
    perfil = u.perfil_estendido
    # Usar o secret claro devolvido pelo setup para confirmar
    valid_token = pyotp.TOTP(secret_plain).now()
    resp_confirm = client.post(confirm_view, {"token": valid_token})
    assert resp_confirm.status_code == 200, resp_confirm.content
    # Fallback: garantir que perfil.totp_secret existe para próximas operações
    perfil.refresh_from_db()
    if not perfil.totp_secret:
        # Deve existir; se não, falha explícita para investigação
        raise AssertionError("perfil.totp_secret ausente após setup/confirm")
    # Agora vamos usar o endpoint verify para gerar falhas
    verify_url = reverse("user_management:2fa_verify")
    # Gerar um token inválido garantido (token válido + 1 mod 1e6)
    current_valid = pyotp.TOTP(secret_plain).now()
    invalid_int = (int(current_valid) + 1) % 1000000
    invalid_token = str(invalid_int).zfill(6)
    # Reset defensivo dos contadores (evita interferência de sinais ou execuções prévias)
    perfil.refresh_from_db()
    perfil.failed_2fa_attempts = 0
    perfil.twofa_failure_count = 0
    perfil.twofa_locked_until = None
    perfil.save(update_fields=["failed_2fa_attempts", "twofa_failure_count", "twofa_locked_until"])
    # Falhar (threshold - 1) vezes retorna 400
    statuses = []
    for i in range(settings.TWOFA_LOCK_THRESHOLD - 1):
        r = client.post(verify_url, {"token": invalid_token})
        statuses.append(r.status_code)
        assert r.status_code == 400, f"Tentativa {i + 1} deveria ser 400, obtidos: {statuses}"
    # Tentativa que atinge o threshold gera lock (>= threshold)
    resp_lock = client.post(verify_url, {"token": invalid_token})
    assert resp_lock.status_code == 423


@pytest.mark.django_db
def test_twofa_alert_email_cooldown(client, auth_user, settings, monkeypatch):
    sent = {}

    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently=True):
        sent.setdefault("count", 0)
        sent["count"] += 1

    monkeypatch.setattr("user_management.views.send_mail", fake_send_mail)
    settings.TWOFA_ALERT_THRESHOLDS = (3,)
    settings.TWOFA_ALERT_EMAIL_COOLDOWN_MINUTES = 10
    # Evitar que lock interfira no teste de cooldown
    settings.TWOFA_LOCK_THRESHOLD = 999
    settings.TWOFA_GLOBAL_IP_LIMIT = 1000
    settings.TWOFA_GLOBAL_IP_WINDOW = 60
    u, tenant, _ = auth_user(username="alertx")
    # Garantir que usuário tem email válido para envio
    u.email = "alertx@example.com"
    u.save(update_fields=["email"])
    setup = reverse("user_management:2fa_setup")
    client.post(setup)
    confirm = reverse("user_management:2fa_confirm")
    # Fazer 3 falhas -> dispara email 1 vez
    for _i in range(3):
        client.post(confirm, {"token": "000000"})
    assert sent.get("count", 0) == 1
    # Repetir mais falhas dentro do cooldown não aumenta
    for _i in range(5):
        client.post(confirm, {"token": "000000"})
    assert sent.get("count", 0) == 1
    # Limpar cache para simular expiração e atingir threshold novamente
    cache.clear()
    # Reset cumulativo para poder alcançar novamente o threshold exato (já que lógica usa igualdade)
    perfil = u.perfil_estendido
    perfil.failed_2fa_attempts = 0
    perfil.twofa_failure_count = 0
    perfil.save(update_fields=["failed_2fa_attempts", "twofa_failure_count"])
    for _i in range(3):
        client.post(confirm, {"token": "000000"})
    assert sent.get("count", 0) == 2

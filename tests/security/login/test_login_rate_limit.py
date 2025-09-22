import time

import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_login_global_rate_limit_blocks_after_threshold(client, settings):
    settings.LOGIN_GLOBAL_RATE_LIMIT_ATTEMPTS = 5
    settings.LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS = 60
    User.objects.create_user(username="ratelimit", password="secret123")
    url = reverse("core:login")
    # Enviar 6 tentativas com senha errada para estourar limite
    for _i in range(5):
        resp = client.post(url, {"username": "ratelimit", "password": "wrong"})
        assert resp.status_code == 200  # página login reapresentada
    # 6a tentativa deve disparar mensagem de bloqueio (mesmo status 200, mas com texto)
    resp_block = client.post(url, {"username": "ratelimit", "password": "wrong"})
    assert resp_block.status_code == 200
    assert b"Muitas tentativas de login deste IP" in resp_block.content


@pytest.mark.django_db
def test_login_after_rate_limit_allows_after_window(client, settings, monkeypatch):
    settings.LOGIN_GLOBAL_RATE_LIMIT_ATTEMPTS = 2
    settings.LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS = 1  # janela curta
    User.objects.create_user(username="ratelimit2", password="secret123")
    url = reverse("core:login")
    client.post(url, {"username": "ratelimit2", "password": "wrong"})
    client.post(url, {"username": "ratelimit2", "password": "wrong"})
    blocked = client.post(url, {"username": "ratelimit2", "password": "wrong"})
    assert b"Muitas tentativas" in blocked.content
    time.sleep(1.2)
    # Após janela, ainda com senha errada, contador reinicia permitindo pelo menos uma tentativa sem msg bloqueio
    resp = client.post(url, {"username": "ratelimit2", "password": "wrong"})
    assert b"Muitas tentativas" not in resp.content

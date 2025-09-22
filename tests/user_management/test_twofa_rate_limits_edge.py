import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from user_management.twofa import get_rate_messages, global_ip_rate_limit_check, rate_limit_check

User = get_user_model()


@pytest.mark.django_db
def test_global_ip_rate_limit_increments_metric(settings):
    # Reduzir limites para teste rápido
    settings.TWOFA_GLOBAL_IP_LIMIT = 1
    settings.TWOFA_GLOBAL_IP_WINDOW = 60

    ip = "1.2.3.4"
    cache.delete("twofa_global_ip_block_metric")

    assert global_ip_rate_limit_check(ip, limit=1, window_seconds=60) is True
    # Segunda tentativa deve estourar e incrementar métrica
    assert global_ip_rate_limit_check(ip, limit=1, window_seconds=60) is False
    cur = cache.get("twofa_global_ip_block_metric", 0) or 0
    assert cur >= 1


@pytest.mark.django_db
def test_user_ip_rate_limit_window():
    user_id = 123
    ip = "5.6.7.8"
    cache.delete(f"2fa:rl:{user_id}:{ip}")

    # Limite 2 em janela pequena
    ok1 = rate_limit_check(user_id, ip, limit=2, window_seconds=5)
    ok2 = rate_limit_check(user_id, ip, limit=2, window_seconds=5)
    ok3 = rate_limit_check(user_id, ip, limit=2, window_seconds=5)

    assert ok1 is True and ok2 is True and ok3 is False

    # Reset expirando a janela
    cache.delete(f"2fa:rl:{user_id}:{ip}")
    assert rate_limit_check(user_id, ip, limit=1, window_seconds=5) is True


def test_rate_messages_contract():
    msgs = get_rate_messages()
    assert set(msgs.keys()) == {"global_ip", "micro", "lock"}
    assert all(isinstance(v, str) and v for v in msgs.values())

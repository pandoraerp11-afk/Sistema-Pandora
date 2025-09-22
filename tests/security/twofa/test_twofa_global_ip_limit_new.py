import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.core.cache import cache

from user_management.twofa import global_ip_rate_limit_check

User = get_user_model()


@pytest.mark.django_db
def test_twofa_global_ip_limit_blocks_independent_users(settings):
    settings.TWOFA_GLOBAL_IP_LIMIT = 5
    settings.TWOFA_GLOBAL_IP_WINDOW = 30
    cache.clear()
    ip = "10.0.0.1"
    [User.objects.create_user(f"u{i}", password="x") for i in range(3)]
    # Consumir 5 tentativas globais (misturando usuários)
    allowed = []
    for _i in range(5):
        allowed.append(global_ip_rate_limit_check(ip))
    assert all(allowed)
    # 6a deve bloquear
    assert global_ip_rate_limit_check(ip) is False
    # Mesmo outro user com rate individual dentro não passa porque global bloqueou
    assert global_ip_rate_limit_check(ip) is False

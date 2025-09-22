import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import authenticate, get_user_model
from django.test import override_settings

User = get_user_model()


@pytest.mark.django_db
def test_login_fail_threshold_custom(settings):
    settings.LOGIN_FAIL_THRESHOLD = 2
    settings.LOGIN_BLOCK_MINUTES = 5
    u = User.objects.create_user("thruser", password="right")
    # 1a falha
    assert authenticate(username="thruser", password="x") is None
    u.refresh_from_db()
    assert u.perfil_estendido.status != "bloqueado"
    # 2a falha atinge limite
    assert authenticate(username="thruser", password="y") is None
    u.refresh_from_db()
    assert u.perfil_estendido.status == "bloqueado"


@pytest.mark.django_db
@override_settings(LOGIN_FAIL_THRESHOLD=3, LOGIN_BLOCK_MINUTES=1)
def test_login_fail_threshold_override_decorator():
    u = User.objects.create_user("thruser2", password="right")
    for _i in range(2):
        assert authenticate(username="thruser2", password="bad") is None
    u.refresh_from_db()
    # Ainda não bloqueou
    assert u.perfil_estendido.status != "bloqueado"
    # 3a falha bloqueia
    assert authenticate(username="thruser2", password="bad3") is None
    u.refresh_from_db()
    assert u.perfil_estendido.status == "bloqueado"

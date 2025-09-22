import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import get_user_model

from user_management.models import LogAtividadeUsuario
from user_management.services.logging_service import log_activity


@pytest.mark.django_db
def test_log_activity_ip_fallback():
    User = get_user_model()
    u = User.objects.create_user(username="u1", password="x")
    # Chama sem ip explícito
    log_activity(u, "TEST", "USER_MGMT", "Descricao de teste sem ip")
    entry = LogAtividadeUsuario.objects.latest("id")
    assert entry.ip_address == "0.0.0.0"
    assert entry.user_agent == "N/A"
    # Chama com ip vazio
    log_activity(u, "TEST", "USER_MGMT", "Descricao ip vazio", ip="")
    entry2 = LogAtividadeUsuario.objects.latest("id")
    assert entry2.ip_address == "0.0.0.0"

import pytest
from django.contrib.auth import get_user_model

from user_management.models import LogAtividadeUsuario
from user_management.services.logging_service import log_activity

pytestmark = [pytest.mark.django_db]


def test_log_activity_creates_entry_and_truncates():
    User = get_user_model()
    u = User.objects.create_user("logger1", password="x")
    long_txt = "X" * 500
    log_activity(
        u, "VERY_LONG_ACTION_NAME_EXCEEDING_LIMIT", "MODULO_MUITO_LONGO_EXCEDE", long_txt, ip="", user_agent=None
    )
    entry = LogAtividadeUsuario.objects.first()
    assert entry is not None
    assert len(entry.acao) <= 100
    assert len(entry.modulo) <= 50
    assert len(entry.descricao) <= 255
    assert entry.ip_address == "0.0.0.0"
    assert entry.user_agent == "N/A"


def test_log_activity_no_user_noop():
    # Não deve criar nada
    before = LogAtividadeUsuario.objects.count()
    log_activity(None, "A", "M", "Desc")  # type: ignore[arg-type]
    assert LogAtividadeUsuario.objects.count() == before


import pytest

User = get_user_model()


@pytest.mark.django_db
def test_log_activity_basic():
    u = User.objects.create_user("logu", password="x")
    log_activity(u, "LOGIN", "user_management", "Usuario entrou", ip="", user_agent="UA/1.0")
    entry = LogAtividadeUsuario.objects.filter(user=u, acao="LOGIN").first()
    assert entry is not None
    assert entry.ip_address == "0.0.0.0"  # fallback aplicado
    assert entry.user_agent == "UA/1.0"


@pytest.mark.django_db
def test_log_activity_safety_truncation():
    u = User.objects.create_user("logu2", password="x")
    big = "x" * 500
    log_activity(u, big, big, big, ip=None, user_agent=None)
    e = LogAtividadeUsuario.objects.filter(user=u).first()
    assert len(e.acao) <= 100
    assert len(e.modulo) <= 50
    assert len(e.descricao) <= 255
    assert e.ip_address == "0.0.0.0"
    assert e.user_agent == "N/A"


@pytest.mark.django_db
def test_log_activity_ignores_none_user():
    # Chamada não deve lançar exceção nem criar log
    log_activity(None, "LOGIN", "user_management", "Sem usuario")  # type: ignore
    assert LogAtividadeUsuario.objects.count() == 0

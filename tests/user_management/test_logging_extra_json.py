import pytest
from django.contrib.auth import get_user_model

from user_management.models import LogAtividadeUsuario
from user_management.services.logging_service import log_activity

User = get_user_model()


@pytest.mark.django_db
def test_log_activity_extra_json_persist():
    u = User.objects.create(username="logjson")
    log_activity(u, "LOGIN", "AUTH", "Login", extra={"k": "v", "n": 1})
    rec = LogAtividadeUsuario.objects.get(user=u)
    assert '"k": "v"' in (rec.extra_json or "")
    assert '"n": 1' in (rec.extra_json or "")

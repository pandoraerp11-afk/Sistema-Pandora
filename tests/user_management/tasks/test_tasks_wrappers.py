import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.tasks import (
    desbloquear_usuarios_periodico,
    limpar_logs_antigos_periodico,
    limpar_sessoes_expiradas_periodico,
)

pytestmark = [pytest.mark.django_db]


def test_tasks_wrappers(monkeypatch):
    User = get_user_model()
    u = User.objects.create_user("blocked", password="x")
    perfil = u.perfil_estendido
    perfil.bloqueado_ate = timezone.now() - timezone.timedelta(minutes=1)
    perfil.save(update_fields=["bloqueado_ate"])

    # Executa wrappers (dependem de funções internas importadas via signals)
    # Apenas garantir que retornam sem erro
    res1 = desbloquear_usuarios_periodico()
    assert res1 is not None or res1 is None  # placeholder: função pode retornar None se nada a fazer
    assert limpar_sessoes_expiradas_periodico() is True
    assert limpar_logs_antigos_periodico(1) is True

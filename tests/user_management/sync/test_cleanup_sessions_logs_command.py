import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import management
from django.utils import timezone

from user_management.models import LogAtividadeUsuario, SessaoUsuario

User = get_user_model()


@pytest.mark.django_db
def test_cleanup_sessions_logs_dry_run(capsys):
    # Criar user e session expirada
    u = User.objects.create_user("u1", "u1@example.com", "x")
    # Criar sessão django expirada manualmente
    Session.objects.create(
        session_key="abc", session_data="Nm9uZQ==", expire_date=timezone.now() - timezone.timedelta(days=1)
    )
    SessaoUsuario.objects.create(user=u, session_key="abc", ip_address="127.0.0.1", user_agent="X", ativa=True)
    # Criar log antigo
    old_log = LogAtividadeUsuario.objects.create(
        user=u, acao="TEST", descricao="x", ip_address="127.0.0.1", user_agent="UA"
    )
    # auto_now_add ignora valor passado; ajustar manualmente
    LogAtividadeUsuario.objects.filter(pk=old_log.pk).update(timestamp=timezone.now() - timezone.timedelta(days=120))
    management.call_command("cleanup_sessions_logs", "--dry-run", "--logs-days=90")
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "Sessões expiradas a desativar: 1" in out
    assert "Logs a remover (> 90 dias): 1" in out
    # Nada alterado
    assert SessaoUsuario.objects.filter(ativa=True).count() == 1
    assert LogAtividadeUsuario.objects.filter(id=old_log.id).exists()


@pytest.mark.django_db
def test_cleanup_sessions_logs_execute():
    u = User.objects.create_user("u2", "u2@example.com", "x")
    Session.objects.create(
        session_key="xyz", session_data="Nm9uZQ==", expire_date=timezone.now() - timezone.timedelta(days=1)
    )
    SessaoUsuario.objects.create(user=u, session_key="xyz", ip_address="127.0.0.1", user_agent="X", ativa=True)
    old_log = LogAtividadeUsuario.objects.create(
        user=u, acao="TEST", descricao="x", ip_address="127.0.0.1", user_agent="UA"
    )
    LogAtividadeUsuario.objects.filter(pk=old_log.pk).update(timestamp=timezone.now() - timezone.timedelta(days=200))
    management.call_command("cleanup_sessions_logs", "--logs-days=90")
    # Sessão marcada inativa e log removido
    assert SessaoUsuario.objects.filter(ativa=True).count() == 0
    assert not LogAtividadeUsuario.objects.filter(id=old_log.id).exists()

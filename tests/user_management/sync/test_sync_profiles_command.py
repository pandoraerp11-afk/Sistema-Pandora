import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from user_management.models import PerfilUsuarioEstendido

User = get_user_model()


@pytest.mark.django_db
def test_sync_profiles_creates_missing(capsys):
    u = User.objects.create_user("noprof", password="x")
    # Remover perfil para simular ausência
    PerfilUsuarioEstendido.objects.filter(user=u).delete()
    call_command("sync_profiles", "--dry-run", "--verbose")
    out = capsys.readouterr().out
    assert "Criaria perfil para noprof" in out
    # Executar real
    call_command("sync_profiles")
    assert PerfilUsuarioEstendido.objects.filter(user=u).exists()

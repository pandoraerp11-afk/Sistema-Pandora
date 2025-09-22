import pytest
from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido, StatusUsuario

User = get_user_model()


@pytest.mark.django_db
def test_reverse_sync_perfil_status_to_user_is_active():
    u = User.objects.create_user(username="rev", password="x", is_active=True)
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    # Alterar perfil para INATIVO deve refletir em user.is_active False via signal
    perfil.status = StatusUsuario.INATIVO
    perfil.save(update_fields=["status"])
    u.refresh_from_db()
    assert u.is_active is False
    # Voltar para ATIVO reativa user
    perfil.status = StatusUsuario.ATIVO
    perfil.save(update_fields=["status"])
    perfil.refresh_from_db()
    u.refresh_from_db()
    assert u.is_active is True


@pytest.mark.django_db
def test_reverse_sync_does_not_force_pending_user_activation():
    u = User.objects.create_user(username="rev2", password="x", is_active=False)
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.PENDENTE
    perfil.save(update_fields=["status"])
    u.refresh_from_db()
    # PENDENTE não altera is_active
    assert u.is_active is False

import pytest
from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido, StatusUsuario
from user_management.services.profile_service import ensure_profile, sync_status

User = get_user_model()


@pytest.mark.django_db
def test_ensure_profile_initial_status_inactive_user():
    # Usuário criado inativo deve gerar perfil com status INATIVO
    u = User.objects.create_user("u_inactive", password="x", is_active=False)
    perfil = ensure_profile(u)
    assert perfil.status == StatusUsuario.INATIVO
    # Chamar novamente não cria duplicata
    again = ensure_profile(u)
    assert again.pk == perfil.pk
    assert PerfilUsuarioEstendido.objects.filter(user=u).count() == 1


@pytest.mark.django_db
def test_sync_status_promotes_after_user_reactivation():
    # Usuário inicialmente inativo -> perfil criado INATIVO
    u = User.objects.create_user("u_inativo2", password="x", is_active=False)
    perfil = ensure_profile(u)
    assert perfil.status == StatusUsuario.INATIVO
    # Reativar usuário e sincronizar -> perfil deve ir para ATIVO
    u.is_active = True
    u.save(update_fields=["is_active"])
    sync_status(u)
    perfil.refresh_from_db()
    assert perfil.status == StatusUsuario.ATIVO

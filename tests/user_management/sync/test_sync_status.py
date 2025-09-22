import pytest
from django.contrib.auth import get_user_model

from user_management.models import StatusUsuario

User = get_user_model()


@pytest.mark.django_db
def test_sync_status_user_active_toggle():
    u = User.objects.create_user("syncuser", password="x", is_active=True)
    perfil = u.perfil_estendido
    assert perfil.status in (StatusUsuario.ATIVO, StatusUsuario.INATIVO)
    # Desativar user e salvar -> signal sync_status deve refletir INATIVO
    u.is_active = False
    u.save(update_fields=["is_active"])
    perfil.refresh_from_db()
    assert perfil.status == StatusUsuario.INATIVO
    # Reativar
    u.is_active = True
    u.save(update_fields=["is_active"])
    perfil.refresh_from_db()
    assert perfil.status == StatusUsuario.ATIVO

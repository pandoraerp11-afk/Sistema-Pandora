import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.models import PerfilUsuarioEstendido, StatusUsuario

pytestmark = [pytest.mark.django_db]


def test_pode_fazer_login_lockout_window():
    User = get_user_model()
    u = User.objects.create_user("locky", password="x", is_active=True)
    # Perfil já criado pelo sinal; obter e ajustar status
    try:
        perfil = u.perfil_estendido  # type: ignore[attr-defined]
    except AttributeError:
        perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=u)
    if perfil.status != StatusUsuario.ATIVO:
        perfil.status = StatusUsuario.ATIVO
        perfil.save(update_fields=["status"])
    assert perfil.pode_fazer_login is True
    perfil.bloqueado_ate = timezone.now() + timezone.timedelta(minutes=5)
    perfil.save(update_fields=["bloqueado_ate"])
    perfil.refresh_from_db()
    assert perfil.pode_fazer_login is False
    # Expira
    perfil.bloqueado_ate = timezone.now() - timezone.timedelta(seconds=5)
    perfil.save(update_fields=["bloqueado_ate"])
    perfil.refresh_from_db()
    assert perfil.pode_fazer_login is True

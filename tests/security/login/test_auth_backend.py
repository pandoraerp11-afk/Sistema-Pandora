import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.models import StatusUsuario

User = get_user_model()


@pytest.mark.django_db
def test_login_bloqueado_por_status(client):
    u = User.objects.create_user(username="u1", password="x", is_active=True)
    perfil = getattr(u, "perfil_estendido", None)
    if perfil:
        perfil.status = StatusUsuario.BLOQUEADO
        perfil.save(update_fields=["status"])
    resp = client.post("/core/login/", {"username": "u1", "password": "x"})
    # Backend retorna None -> login view normalmente retorna 200 com form ou mantém redirect? Observado 302 para /core/login/
    assert resp.status_code in (200, 302)
    assert resp.wsgi_request.user.is_anonymous


@pytest.mark.django_db
def test_login_bloqueio_temporal(client):
    u = User.objects.create_user(username="u2", password="x", is_active=True)
    perfil = getattr(u, "perfil_estendido", None)
    if perfil:
        perfil.bloqueado_ate = timezone.now() + timezone.timedelta(minutes=5)
        perfil.save(update_fields=["bloqueado_ate"])
    resp = client.post("/core/login/", {"username": "u2", "password": "x"})
    assert resp.status_code in (200, 302)
    assert resp.wsgi_request.user.is_anonymous


@pytest.mark.django_db
def test_login_reset_tentativas(client):
    u = User.objects.create_user(username="u3", password="x", is_active=True)
    perfil = getattr(u, "perfil_estendido", None)
    if perfil:
        perfil.tentativas_login_falhadas = 3
        perfil.save(update_fields=["tentativas_login_falhadas"])
    resp = client.post("/core/login/", {"username": "u3", "password": "x"})
    assert resp.status_code in (302, 303)
    perfil.refresh_from_db()
    assert perfil.tentativas_login_falhadas == 0, f"Tentativas nao resetadas: {perfil.tentativas_login_falhadas}"

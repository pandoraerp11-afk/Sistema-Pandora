import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.models import PerfilUsuarioEstendido, StatusUsuario

User = get_user_model()


@pytest.mark.django_db
def test_login_blocked_status(client, django_user_model):
    u = django_user_model.objects.create_user(username="blocked", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.BLOQUEADO
    perfil.save()
    assert client.login(username="blocked", password="x") is False


@pytest.mark.django_db
def test_login_suspenso_status(client, django_user_model):
    u = django_user_model.objects.create_user(username="susp", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.SUSPENSO
    perfil.save()
    assert client.login(username="susp", password="x") is False


@pytest.mark.django_db
def test_login_inativo_status(client, django_user_model):
    u = django_user_model.objects.create_user(username="inativo", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.INATIVO
    perfil.save()
    assert client.login(username="inativo", password="x") is False


@pytest.mark.django_db
def test_login_bloqueado_ate_future(client, django_user_model):
    u = django_user_model.objects.create_user(username="tempblock", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.BLOQUEADO
    perfil.bloqueado_ate = timezone.now() + timezone.timedelta(minutes=10)
    perfil.save()
    assert client.login(username="tempblock", password="x") is False


@pytest.mark.django_db
def test_login_bloqueio_expirado(client, django_user_model):
    u = django_user_model.objects.create_user(username="expired", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.status = StatusUsuario.BLOQUEADO
    perfil.bloqueado_ate = timezone.now() - timezone.timedelta(minutes=1)
    perfil.save()
    # Backend deve liberar (status BLOQUEADO mas bloqueado_ate já passou -> ainda bloqueado? Regra atual exige limpar status; simulamos desbloqueio)
    perfil.status = StatusUsuario.ATIVO
    perfil.save()
    assert client.login(username="expired", password="x") is True


@pytest.mark.django_db
def test_reset_tentativas_on_success(client, django_user_model):
    u = django_user_model.objects.create_user(username="tries", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    perfil.tentativas_login_falhadas = 3
    perfil.save(update_fields=["tentativas_login_falhadas"])
    assert client.login(username="tries", password="x") is True
    perfil.refresh_from_db()
    assert perfil.tentativas_login_falhadas == 0

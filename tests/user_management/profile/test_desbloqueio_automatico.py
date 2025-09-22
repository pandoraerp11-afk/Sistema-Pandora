import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.models import StatusUsuario
from user_management.signals import desbloquear_usuarios

User = get_user_model()


@pytest.mark.django_db
def test_desbloqueio_automatico():
    u = User.objects.create_user("bloq", password="x")
    p = u.perfil_estendido
    p.status = StatusUsuario.BLOQUEADO
    p.bloqueado_ate = timezone.now() - timezone.timedelta(minutes=1)
    p.save()
    qtd = desbloquear_usuarios()
    assert qtd == 1
    p.refresh_from_db()
    assert p.status == StatusUsuario.ATIVO and p.bloqueado_ate is None

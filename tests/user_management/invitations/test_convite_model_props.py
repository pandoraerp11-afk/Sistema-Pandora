import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from user_management.models import ConviteUsuario, TipoUsuario

pytestmark = [pytest.mark.django_db]


def test_convite_properties_usage_and_expiration():
    User = get_user_model()
    admin = User.objects.create_user("adminX", password="x")
    futuro = timezone.now() + timezone.timedelta(days=1)
    convite = ConviteUsuario.objects.create(
        email="novo@example.com",
        tipo_usuario=TipoUsuario.FUNCIONARIO,
        expirado_em=futuro,
        enviado_por=admin,
        tenant=None,
    )
    assert convite.pode_ser_usado is True
    convite.usado = True
    convite.save(update_fields=["usado"])
    convite.refresh_from_db()
    assert convite.pode_ser_usado is False
    # Expirado
    convite.usado = False
    convite.expirado_em = timezone.now() - timezone.timedelta(seconds=5)
    convite.save(update_fields=["usado", "expirado_em"])
    convite.refresh_from_db()
    assert convite.pode_ser_usado is False

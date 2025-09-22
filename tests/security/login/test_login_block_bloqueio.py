import pytest

pytestmark = [pytest.mark.login, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from user_management.models import StatusUsuario

User = get_user_model()


@pytest.mark.django_db
def test_bloqueio_apos_5_falhas(client):
    u = User.objects.create_user(username="failuser", password="correta", is_active=True)
    perfil = u.perfil_estendido
    # 5 tentativas com senha errada
    for _i in range(5):
        client.post("/core/login/", {"username": "failuser", "password": "errada"})
    perfil.refresh_from_db()
    assert perfil.status == StatusUsuario.BLOQUEADO
    assert perfil.bloqueado_ate is not None and perfil.bloqueado_ate > timezone.now()
    # Mesmo com senha correta agora não loga
    resp = client.post("/core/login/", {"username": "failuser", "password": "correta"})
    assert resp.wsgi_request.user.is_anonymous


@pytest.mark.django_db
def test_convite_aceito_tipo_usuario_status(client, django_user_model):
    # Simular fluxo mínimo de convite: criar objeto convite e aceitar
    from django.utils import timezone

    from core.models import Tenant
    from user_management.models import ConviteUsuario, TipoUsuario

    tenant = Tenant.objects.create(nome="Empresa X", slug="empresax") if hasattr(Tenant.objects, "create") else None
    convite = ConviteUsuario.objects.create(
        email="novo@example.com",
        tipo_usuario=TipoUsuario.CLIENTE,
        expirado_em=timezone.now() + timezone.timedelta(days=1),
        enviado_por=django_user_model.objects.create_user("adminsender", "adm@x.com", "x"),
        tenant=tenant,
    )
    # Acessar página de convite (GET)
    url = reverse("user_management:aceitar_convite", args=[convite.token])
    resp = client.get(url)
    assert resp.status_code == 200
    # Post para criar usuário
    post_data = {
        "username": "novousuario",
        "password1": "SenhaComplexa123",
        "password2": "SenhaComplexa123",
        "email": convite.email,
        "tipo_usuario": convite.tipo_usuario,
    }
    resp2 = client.post(url, post_data)
    assert resp2.status_code in (302, 303)
    novo = User.objects.get(username="novousuario")
    perfil_novo = novo.perfil_estendido
    assert perfil_novo.tipo_usuario == convite.tipo_usuario
    assert perfil_novo.status == StatusUsuario.ATIVO

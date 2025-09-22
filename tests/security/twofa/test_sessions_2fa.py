import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
from django.contrib.auth import get_user_model
from django.urls import reverse

from user_management.models import LogAtividadeUsuario, SessaoUsuario

User = get_user_model()


@pytest.mark.django_db
def test_bulk_session_termination_and_log(client, django_user_model):
    # Criar usuário e simular 3 sessões
    u = django_user_model.objects.create_user("multi", "multi@example.com", "x")
    # Criar tenant e vínculo para evitar redirect do middleware
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="Empresa Teste", slug="empresateste")
    TenantUser.objects.create(user=u, tenant=tenant)
    sess = client.session
    sess["tenant_id"] = tenant.id
    sess.save()
    # Simular sessões
    for i in range(3):
        SessaoUsuario.objects.create(user=u, session_key=f"sess{i}", ip_address="127.0.0.1", user_agent="test-agent")
    assert SessaoUsuario.objects.filter(user=u, ativa=True).count() == 3
    client.force_login(u)
    # Executar bulk terminate via POST JSON
    ids = list(SessaoUsuario.objects.filter(user=u).values_list("id", flat=True))
    url = reverse("user_management:sessao_encerrar_multiplas")
    resp = client.post(url, data={"ids": ",".join(map(str, ids))}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert resp.status_code == 200
    # Verificar encerradas
    assert SessaoUsuario.objects.filter(user=u, ativa=True).count() == 0
    # Assert log de bulk termination
    assert LogAtividadeUsuario.objects.filter(user=u, acao="TERMINATE_BULK_SESSIONS").exists(), (
        "Log TERMIANTE_BULK_SESSIONS não registrado"
    )


@pytest.mark.django_db
def test_toggle_2fa(client, django_user_model):
    u = django_user_model.objects.create_user("user2fa", "2fa@example.com", "x")
    perfil = u.perfil_estendido
    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(nome="Empresa Teste 2", slug="empresateste2")
    TenantUser.objects.create(user=u, tenant=tenant)
    sess = client.session
    sess["tenant_id"] = tenant.id
    sess.save()
    assert perfil.autenticacao_dois_fatores is False
    client.force_login(u)
    url = reverse("user_management:toggle_2fa", args=[perfil.pk])
    resp = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert resp.status_code == 200
    perfil.refresh_from_db()
    assert perfil.autenticacao_dois_fatores is True
    assert LogAtividadeUsuario.objects.filter(user=u, acao="TOGGLE_2FA").count() == 1
    # Toggle again
    resp2 = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert resp2.status_code == 200
    perfil.refresh_from_db()
    assert perfil.autenticacao_dois_fatores is False
    assert LogAtividadeUsuario.objects.filter(user=u, acao="TOGGLE_2FA").count() == 2

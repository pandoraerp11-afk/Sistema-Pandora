import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
import pyotp
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_twofa_admin_reset(client):
    # superuser
    admin = User.objects.create_superuser("admin", "admin@example.com", "x")
    # target user
    u = User.objects.create_user("victim", "victim@example.com", "x")
    t = Tenant.objects.create(nome="Empresa Admin", slug="empadmin")
    TenantUser.objects.create(user=u, tenant=t)
    sess = client.session
    sess["tenant_id"] = t.id
    sess.save()
    client.force_login(u)
    # habilita 2FA
    setup = client.post(reverse("user_management:2fa_setup"))
    secret = setup.json()["secret"]
    token = pyotp.TOTP(secret).now()
    c = client.post(reverse("user_management:2fa_confirm"), {"token": token})
    assert c.status_code == 200
    # switch para admin e reset
    client.force_login(admin)
    r = client.post(reverse("user_management:2fa_admin_reset"), {"user_id": u.id})
    assert r.status_code == 200, r.content
    # verifica que user perdeu 2FA
    u.refresh_from_db()
    perfil = u.perfil_estendido
    assert not perfil.autenticacao_dois_fatores
    assert perfil.totp_secret is None

import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
import pyotp
from django.urls import reverse


@pytest.mark.django_db
def test_twofa_enforcement_redirect(client, auth_user):
    u, t, _ = auth_user(username="bob")
    # Tornar admin do tenant (atualiza TenantUser existente)
    tu = u.tenant_memberships.first()
    tu.is_tenant_admin = True
    tu.save(update_fields=["is_tenant_admin"])
    # Setup + confirm 2FA
    setup_url = reverse("user_management:2fa_setup")
    r = client.post(setup_url)
    secret = r.json()["secret"]
    token = pyotp.TOTP(secret).now()
    confirm_url = reverse("user_management:2fa_confirm")
    c = client.post(confirm_url, {"token": token})
    assert c.status_code == 200, f"Confirm falhou status={c.status_code} body={getattr(c, 'content', b'')!r}"
    # Acesso a rota protegida deve redirecionar para challenge até verificação
    protected = reverse("user_management:usuario_list")
    resp = client.get(protected)
    assert resp.status_code in (301, 302)
    assert "/user-management/2fa/challenge/" in resp.url
    # Verifica
    token2 = pyotp.TOTP(secret).now()
    verify_url = reverse("user_management:2fa_verify")
    v = client.post(verify_url, {"token": token2})
    assert v.status_code == 200, f"Verify falhou status={v.status_code} body={getattr(v, 'content', b'')!r}"
    # Agora acesso deve funcionar
    resp2 = client.get(protected, follow=False)
    assert resp2.status_code == 200, (
        f"Esperado 200 após verificação; obtido {resp2.status_code} redirect para {resp2.headers.get('Location')} session_keys={list(client.session.keys())}"
    )

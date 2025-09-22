import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]
import pyotp
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant, TenantUser

User = get_user_model()


@pytest.mark.django_db
def test_twofa_regenerate_codes(client):
    u = User.objects.create_user("alice", "alice@example.com", "x")
    t = Tenant.objects.create(nome="Empresa Z", slug="empresaz")
    TenantUser.objects.create(user=u, tenant=t, is_tenant_admin=True)
    sess = client.session
    sess["tenant_id"] = t.id
    sess.save()
    client.force_login(u)
    # setup
    setup_url = reverse("user_management:2fa_setup")
    r = client.post(setup_url)
    secret = r.json()["secret"]
    codes_initial = r.json()["recovery_codes"]
    assert len(codes_initial) == 8
    # confirm
    token = pyotp.TOTP(secret).now()
    confirm_url = reverse("user_management:2fa_confirm")
    c = client.post(confirm_url, {"token": token})
    assert c.status_code == 200
    # regenerate
    regenerate_url = reverse("user_management:2fa_regenerate_codes")
    token2 = pyotp.TOTP(secret).now()
    regen = client.post(regenerate_url, {"token": token2})
    assert regen.status_code == 200, regen.content
    data = regen.json()
    assert data["status"] == "ok"
    assert len(data["recovery_codes"]) == 8
    assert data["recovery_codes"] != codes_initial
    # tentar usar código antigo deve falhar
    old_code = codes_initial[0]
    verify_url = reverse("user_management:2fa_verify")
    v = client.post(verify_url, {"recovery_code": old_code})
    assert v.status_code == 400
    # usar código novo funciona
    new_code = data["recovery_codes"][0]
    v2 = client.post(verify_url, {"recovery_code": new_code})
    assert v2.status_code == 200

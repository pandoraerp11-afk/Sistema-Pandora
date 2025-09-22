import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_wizard_metrics_endpoint_staff_only(client):
    """Garante:
    1. Não autenticado -> redirect login
    2. Autenticado não staff -> 403 (ou cadeia terminando em 403 depois de auto-seleção de tenant)
    3. Staff -> 200 com payload esperado
    """
    from core.models import Role, Tenant, TenantUser

    staff = User.objects.create_user(username="staff", email="s@example.com", password="x12345678", is_staff=True)
    user = User.objects.create_user(username="user", email="u@example.com", password="x12345678")

    # Criar tenant e vincular usuário não staff para evitar redirect de seleção
    tenant = Tenant.objects.create(
        name="Empresa X", tipo_pessoa="PJ", cnpj="12345678000199", subdomain="emp-x", status="ATIVO"
    )
    role = Role.objects.create(name="Basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    url = reverse("core:wizard_metrics")

    # 1. Não autenticado
    resp = client.get(url)
    assert resp.status_code in (302, 301)

    # 2. Autenticado não staff
    client.force_login(user)
    resp = client.get(url)
    # Deve ser 403 direto (view faz check manual de staff)
    assert resp.status_code == 403
    client.logout()

    # 3. Staff
    client.force_login(staff)
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "wizard_metrics" in data

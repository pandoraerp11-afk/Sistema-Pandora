import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_legacy_wizard_redirects(client, django_user_model):
    # criar superuser para acessar rotas
    user = django_user_model.objects.create_superuser(username="admin", email="admin@example.com", password="pass")
    client.force_login(user)
    resp_create = client.get("/core/tenants/wizard/")
    # Deve ser redirect permanente (RedirectView permanent=True)
    assert resp_create.status_code == 301
    expected_create = reverse("core:tenant_create")
    location_create = resp_create.headers.get("Location", "")
    assert location_create.endswith(expected_create), (
        f"Location inesperado: {location_create} (esperado sufixo {expected_create})"
    )

    # criar tenant dummy para testar edit redirect
    from core.models import Tenant

    t = Tenant.objects.create(name="Temp Corp", tipo_pessoa="PJ", status="active")
    resp_edit = client.get(f"/core/tenants/wizard/{t.pk}/edit/")
    assert resp_edit.status_code == 301
    expected_edit = reverse("core:tenant_update", kwargs={"pk": t.pk})
    location_edit = resp_edit.headers.get("Location", "")
    assert location_edit.endswith(expected_edit), (
        f"Location inesperado: {location_edit} (esperado sufixo {expected_edit})"
    )

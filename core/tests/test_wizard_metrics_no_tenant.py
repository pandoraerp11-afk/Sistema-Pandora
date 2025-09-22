import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_wizard_metrics_endpoint_staff_no_tenant_selected(client):
    staff = User.objects.create_user(username="staff2", email="s2@example.com", password="x12345678", is_staff=True)
    client.force_login(staff)
    url = reverse("core:wizard_metrics")
    resp = client.get(url)
    assert resp.status_code == 200
    payload = resp.json()
    assert "wizard_metrics" in payload
    # Deve conter chaves counters/latency/last_errors
    metrics = payload["wizard_metrics"]
    assert "counters" in metrics
    assert "latency" in metrics
    assert "last_errors" in metrics

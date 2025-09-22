import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from clientes.models import Cliente
from core.models import Tenant
from portal_cliente.models import ContaCliente

User = get_user_model()


@pytest.mark.django_db
def test_portal_cliente_dashboard(client):
    tenant = Tenant.objects.create(nome="T2", slug="t2")
    user = User.objects.create_user(username="cli1", password="pass")
    cliente = Cliente.objects.create(tenant=tenant, nome="Cliente Z")
    ContaCliente.objects.create(cliente=cliente, usuario=user, ativo=True)
    client.force_login(user)
    url = reverse("portal_cliente:dashboard")
    resp = client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_portal_cliente_sem_conta_404(client):
    user = User.objects.create_user(username="cli2", password="pass")
    client.force_login(user)
    url = reverse("portal_cliente:dashboard")
    resp = client.get(url)
    assert resp.status_code == 404

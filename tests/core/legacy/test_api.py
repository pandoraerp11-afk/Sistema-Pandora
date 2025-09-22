from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, Tenant, TenantUser

CustomUser = get_user_model()


class CoreAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = CustomUser.objects.create_superuser("superuser", "super@example.com", "password123")
        self.admin_user = CustomUser.objects.create_user("adminuser", "admin@example.com", "password123")
        self.regular_user = CustomUser.objects.create_user("regularuser", "regular@example.com", "password123")
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="teste")
        self.admin_role = Role.objects.create(tenant=self.tenant, name="Admin")
        self.user_role = Role.objects.create(tenant=self.tenant, name="Usuário")
        TenantUser.objects.create(tenant=self.tenant, user=self.admin_user, role=self.admin_role, is_tenant_admin=True)
        TenantUser.objects.create(tenant=self.tenant, user=self.regular_user, role=self.user_role)

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_list_tenants_api_superuser(self):
        self.authenticate(self.superuser)
        url = reverse("core:api_tenant_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_tenants_api_regular_user_forbidden(self):
        self.authenticate(self.regular_user)
        url = reverse("core:api_tenant_list")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_create_tenant_api_superuser(self):
        self.authenticate(self.superuser)
        url = reverse("core:api_tenant_create")
        payload = {"name": "Empresa API", "subdomain": "empresa-api", "status": "active"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tenant.objects.filter(subdomain="empresa-api").exists())

    def test_create_tenant_api_regular_user_forbidden(self):
        self.authenticate(self.regular_user)
        url = reverse("core:api_tenant_create")
        payload = {"name": "Empresa API 2", "subdomain": "empresa-api2", "status": "active"}
        response = self.client.post(url, payload, format="json")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_switch_tenant_api(self):
        self.authenticate(self.admin_user)
        url = reverse("core:api_switch_tenant", args=[self.tenant.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.session.get("tenant_id"), self.tenant.id)

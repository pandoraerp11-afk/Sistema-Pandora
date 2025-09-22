"""Testes de modelo e view básicos do app administration alinhados ao estado atual."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from admin.models import SystemAlert, TenantMetrics
from core.models import Tenant


class SystemAlertModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste", status="active")
        self.alert = SystemAlert.objects.create(
            tenant=self.tenant,
            title="Alerta de Teste",
            description="Descrição do alerta de teste",
            alert_type="system",
            severity="high",
            status="open",
        )

    def test_alert_creation(self):
        self.assertEqual(self.alert.tenant, self.tenant)
        self.assertEqual(self.alert.title, "Alerta de Teste")
        self.assertEqual(self.alert.description, "Descrição do alerta de teste")
        self.assertEqual(self.alert.alert_type, "system")
        self.assertEqual(self.alert.severity, "high")
        self.assertEqual(self.alert.status, "open")

    def test_alert_str(self):
        self.assertEqual(str(self.alert), "[HIGH] Alerta de Teste")

    def test_acknowledge_alert(self):
        User = get_user_model()
        user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.alert.acknowledge(user)
        self.assertEqual(self.alert.status, "acknowledged")
        self.assertEqual(self.alert.assigned_to, user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_resolve_alert(self):
        self.alert.resolve()
        self.assertEqual(self.alert.status, "resolved")
        self.assertIsNotNone(self.alert.resolved_at)


class TenantMetricsModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste", status="active")
        self.metric = TenantMetrics.objects.create(
            tenant=self.tenant,
            date="2025-06-08",
            active_users=120,
            total_users=150,
            storage_used=1024000,
            api_requests=5000,
        )

    def test_tenant_metric_creation(self):
        self.assertEqual(self.metric.tenant, self.tenant)
        self.assertEqual(self.metric.active_users, 120)
        self.assertEqual(self.metric.total_users, 150)
        self.assertEqual(self.metric.storage_used, 1024000)
        self.assertEqual(self.metric.api_requests, 5000)

    def test_tenant_metric_str(self):
        self.assertEqual(str(self.metric), "Empresa Teste - 2025-06-08")


class AdminHomeViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass123"
        )

    def test_admin_home_requires_login(self):
        url = reverse("administration:admin_home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_admin_home_with_superuser(self):
        self.client.login(username="admin", password="adminpass123")
        url = reverse("administration:admin_home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

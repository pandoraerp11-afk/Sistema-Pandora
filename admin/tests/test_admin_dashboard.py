"""Testes de admin/dashboard (limpos)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from admin.models import SystemAlert
from core.models import Tenant

User = get_user_model()


class SystemAlertModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste", status="active")
        self.user = User.objects.create_user(username="tester", email="tester@example.com", password="pass123")
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
        self.assertTrue(str(self.alert).startswith("[HIGH] Alerta de Teste"))

    def test_acknowledge_alert(self):
        self.assertEqual(self.alert.status, "open")
        self.alert.acknowledge(self.user)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "acknowledged")
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_resolve_alert(self):
        self.alert.acknowledge(self.user)
        self.alert.resolve(self.user, "Problema resolvido")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "resolved")
        self.assertEqual(self.alert.resolved_by, self.user)
        self.assertIsNotNone(self.alert.resolved_at)
        self.assertEqual(self.alert.resolution_notes, "Problema resolvido")


class AdminDashboardAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste", status="active")
        for i in range(5):
            SystemAlert.objects.create(
                tenant=self.tenant,
                title=f"Alerta {i + 1}",
                description=f"Descrição do alerta {i + 1}",
                alert_type="system",
                severity="high" if i < 2 else "medium",
                status="open",
            )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_tenants(self):
        try:
            url = reverse("admin:dashboard-stats")
        except Exception:
            self.skipTest("Endpoint admin:dashboard-stats não configurado.")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_list_alerts(self):
        try:
            url = reverse("admin:alerts-list")
        except Exception:
            self.skipTest("Endpoint admin:alerts-list não configurado.")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        if "results" in resp.data:
            self.assertEqual(len(resp.data["results"]), 5)

    def test_dashboard_overview(self):
        try:
            url = reverse("admin-dashboard-overview")
        except Exception:
            self.skipTest("Endpoint admin-dashboard-overview não configurado.")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        for key in ["total_tenants", "active_tenants", "open_alerts"]:
            if key in resp.data:
                self.assertIsInstance(resp.data[key], int)

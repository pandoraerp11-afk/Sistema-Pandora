"""Testes de admin/dashboard (limpos)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from admin.models import SystemAlert
from core.models import Tenant

if TYPE_CHECKING:
    from django.http import HttpResponse


User = get_user_model()


class SystemAlertModelTest(TestCase):
    """Testes para o modelo SystemAlert."""

    def setUp(self) -> None:
        """Configura o ambiente para os testes do modelo."""
        self.tenant = Tenant.objects.create(
            name="Empresa Teste",
            subdomain="empresa-teste",
            status="active",
        )
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="pass123",  # noqa: S106
        )
        self.alert = SystemAlert.objects.create(
            tenant=self.tenant,
            title="Alerta de Teste",
            description="Descrição do alerta de teste",
            alert_type="system",
            severity="high",
            status="open",
        )

    def test_alert_creation(self) -> None:
        """Testa a criação de um alerta."""
        assert self.alert.tenant == self.tenant
        assert self.alert.title == "Alerta de Teste"
        assert self.alert.description == "Descrição do alerta de teste"
        assert self.alert.alert_type == "system"
        assert self.alert.severity == "high"
        assert self.alert.status == "open"

    def test_alert_str(self) -> None:
        """Testa a representação em string do alerta."""
        assert str(self.alert).startswith("[HIGH] Alerta de Teste")

    def test_acknowledge_alert(self) -> None:
        """Testa o reconhecimento de um alerta."""
        assert self.alert.status == "open"
        self.alert.acknowledge(self.user)
        self.alert.refresh_from_db()
        assert self.alert.status == "acknowledged"
        assert self.alert.acknowledged_by == self.user
        assert self.alert.acknowledged_at is not None

    def test_resolve_alert(self) -> None:
        """Testa a resolução de um alerta."""
        self.alert.acknowledge(self.user)
        self.alert.resolve(self.user, "Problema resolvido")
        self.alert.refresh_from_db()
        assert self.alert.status == "resolved"
        assert self.alert.resolved_by == self.user
        assert self.alert.resolved_at is not None
        assert self.alert.resolution_notes == "Problema resolvido"


class AdminDashboardAPITest(TestCase):
    """Testes para os endpoints da API do dashboard de administração."""

    NUM_HIGH_SEVERITY_ALERTS = 2
    TOTAL_ALERTS = 5

    def setUp(self) -> None:
        """Configura o ambiente para os testes da API."""
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",  # noqa: S106
        )
        # Autenticação de sessão para evitar redirects de middleware/login_required
        self.client.force_login(self.admin_user)
        self.tenant = Tenant.objects.create(
            name="Empresa Teste",
            subdomain="empresa-teste",
            status="active",
        )
        for i in range(self.TOTAL_ALERTS):
            SystemAlert.objects.create(
                tenant=self.tenant,
                title=f"Alerta {i + 1}",
                description=f"Descrição do alerta {i + 1}",
                alert_type="system",
                severity="high" if i < self.NUM_HIGH_SEVERITY_ALERTS else "medium",
                status="open",
            )

    # force_authenticate não necessário após force_login; manter sessão consistente

    def test_list_tenants(self) -> None:
        """Testa a listagem de tenants via API."""
        # Usar namespace 'administration' para evitar colisão com django.contrib.admin
        url = reverse("administration:tenant-list")
        resp: HttpResponse = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Empresa Teste"

    def test_list_alerts(self) -> None:
        """Testa a listagem de alertas via API."""
        url = reverse("administration:system-alerts-list")
        resp: HttpResponse = self.client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        # Suporta resposta paginada (dict) ou lista direta
        if isinstance(data, dict) and "results" in data:
            assert data["count"] == self.TOTAL_ALERTS
            results = data["results"]
        else:
            results = data
            assert len(results) == self.TOTAL_ALERTS
        assert results[0]["title"] == "Alerta 5"  # Ordenação padrão é -created_at

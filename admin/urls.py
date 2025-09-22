# admin/urls.py (Versão Ultra Moderna)

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminActivityViewSet,
    # API ViewSets
    DashboardStatsViewSet,
    # Views baseadas em classe para formulários
    SystemAlertCreateView,
    SystemAlertUpdateView,
    SystemAlertViewSet,
    SystemConfigurationCreateView,
    SystemConfigurationUpdateView,
    SystemConfigurationViewSet,
    TenantBackupViewSet,
    TenantConfigurationUpdateView,
    TenantConfigurationViewSet,
    TenantUsageReportViewSet,
    admin_home,
    alerts_page,
    billing_page,
    configurations_page,
    modules_page,
    reports_page,
    support_page,
)

app_name = "administration"

# --- API Endpoints ---
router = DefaultRouter()
router.register(r"stats", DashboardStatsViewSet, basename="dashboard-stats")
router.register(r"alerts", SystemAlertViewSet, basename="alerts")
router.register(r"tenant-configurations", TenantConfigurationViewSet, basename="tenant-configurations")
router.register(r"activities", AdminActivityViewSet, basename="activities")
router.register(r"system-configurations", SystemConfigurationViewSet, basename="system-configurations")
router.register(r"backups", TenantBackupViewSet, basename="backups")
router.register(r"reports", TenantUsageReportViewSet, basename="reports")


# --- URLs para as Páginas Renderizadas (usadas pelo menu) ---
urlpatterns = [
    # Dashboard home do módulo admin
    path("", admin_home, name="admin_home"),
    # Páginas de visualização modernas
    path("alerts/", alerts_page, name="alerts_page"),
    path("configurations/", configurations_page, name="configurations_page"),
    # Novas páginas para gestão empresarial
    path("modules/", modules_page, name="modules_page"),
    path("reports/", reports_page, name="reports_page"),
    path("billing/", billing_page, name="billing_page"),
    path("support/", support_page, name="support_page"),
    # Formulários de alertas
    path("alerts/create/", SystemAlertCreateView.as_view(), name="alert_create"),
    path("alerts/<int:pk>/edit/", SystemAlertUpdateView.as_view(), name="alert_update"),
    # Formulários de configurações
    path("config/system/create/", SystemConfigurationCreateView.as_view(), name="system_config_create"),
    path("config/system/<int:pk>/edit/", SystemConfigurationUpdateView.as_view(), name="system_config_update"),
    path("config/tenant/", TenantConfigurationUpdateView.as_view(), name="tenant_config_update"),
    # Rotas da API (prefixadas com /api/)
    path("api/", include(router.urls)),
]

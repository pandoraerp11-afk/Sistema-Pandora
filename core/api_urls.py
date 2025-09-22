# core/api_urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views
from .api_views import get_dashboard_metrics

app_name = "core_api"

router = DefaultRouter()
router.register(r"tenants", api_views.TenantViewSet, basename="tenant")
router.register(r"users", api_views.CustomUserViewSet, basename="user")
router.register(r"tenant-users", api_views.TenantUserViewSet, basename="tenant-user")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/", include("rest_framework.urls")),
    path("system/stats/", api_views.system_stats, name="system_stats"),
    path("dashboard/metrics/", get_dashboard_metrics, name="dashboard-metrics"),
]

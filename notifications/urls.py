from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConfiguracaoNotificacaoUpdateView,
    EmailDeliveryViewSet,
    NotificationActionView,
    NotificationDetailView,
    NotificationListView,
    NotificationMetricsViewSet,
    NotificationRuleViewSet,
    NotificationTemplateViewSet,
    NotificationViewSet,
    PreferenciaNotificacaoUpdateView,
    TenantNotificationSettingsViewSet,
    UserNotificationPreferencesViewSet,
    api_notification_action,
    api_notification_batch_action,
    api_notifications_count,
    api_notifications_recent,
    notifications_home,
)

app_name = "notifications"

urlpatterns = [
    # Home
    path("home/", notifications_home, name="notifications_home"),
    # Views principais
    path("", NotificationListView.as_view(), name="notification_list"),
    path("<int:pk>/", NotificationDetailView.as_view(), name="notification_detail"),
    path("<int:pk>/action/", NotificationActionView.as_view(), name="notification_action"),
    # Configurações
    path("preferencias/", PreferenciaNotificacaoUpdateView.as_view(), name="preferencias"),
    path("configuracoes/", ConfiguracaoNotificacaoUpdateView.as_view(), name="configuracoes"),
    # APIs AJAX
    path("api/action/", api_notification_action, name="api_action"),
    path("api/batch-action/", api_notification_batch_action, name="notification-batch-action"),
    path("api/count/", api_notifications_count, name="api_count"),
    path("api/recent/", api_notifications_recent, name="api_recent"),
    # API avançada (DRF)
    path(
        "api/v2/",
        include(
            (
                [
                    # router urls placeholder (adicionado abaixo)
                ],
                "notifications",
            ),
            namespace="api_v2",
        ),
    ),
]

# Router DRF (registrado após urlpatterns base para não conflitar)
router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="adv-notifications")
router.register(r"templates", NotificationTemplateViewSet, basename="notification-templates")
router.register(r"rules", NotificationRuleViewSet, basename="notification-rules")
router.register(r"settings", TenantNotificationSettingsViewSet, basename="notification-settings")
router.register(r"preferences", UserNotificationPreferencesViewSet, basename="notification-preferences")
router.register(r"metrics", NotificationMetricsViewSet, basename="notification-metrics")
router.register(r"email-deliveries", EmailDeliveryViewSet, basename="email-deliveries")

# Anexar rotas do router dentro de api/v2
from django.urls import re_path

urlpatterns += [
    re_path(r"^notifications/api/v2/", include(router.urls)),
]

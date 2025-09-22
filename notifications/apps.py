# notifications/apps.py
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuração do app de notificações"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Sistema de Notificações"

    def ready(self):
        """Executado quando o app está pronto"""

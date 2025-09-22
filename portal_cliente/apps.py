from django.apps import AppConfig


class PortalClienteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal_cliente"
    verbose_name = "Portal Cliente"

    def ready(self):
        try:
            import portal_cliente.signals  # noqa
        except Exception:
            pass

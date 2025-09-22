from django.apps import AppConfig


class PortalFornecedorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal_fornecedor"
    verbose_name = "Portal do Fornecedor"

    def ready(self):
        """Importa signals quando o app estiver carregado."""
        try:
            import portal_fornecedor.signals  # noqa
        except ImportError:
            pass

from django.apps import AppConfig


class CotacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cotacoes"
    verbose_name = "Cotações"

    def ready(self):
        """Importa signals quando o app estiver carregado."""
        try:
            import cotacoes.signals  # noqa
        except ImportError:
            pass

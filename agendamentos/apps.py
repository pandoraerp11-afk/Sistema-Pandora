from django.apps import AppConfig


class AgendamentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agendamentos"
    verbose_name = "Agendamentos"

    def ready(self):
        from . import signals  # noqa: F401

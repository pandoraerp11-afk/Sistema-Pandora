# estoque/apps.py
from django.apps import AppConfig


class EstoqueConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "estoque"  # CORRETO
    verbose_name = "Estoque"  # CORRETO

    def ready(self):
        from . import signals  # noqa: F401 força registro dos handlers

# relatorios/apps.py
from django.apps import AppConfig


class RelatoriosConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "relatorios"  # CORRETO
    verbose_name = "Relatórios"  # CORRETO

# financeiro/apps.py
from django.apps import AppConfig


class FinanceiroConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "financeiro"  # CORRETO
    verbose_name = "Financeiro"  # CORRETO

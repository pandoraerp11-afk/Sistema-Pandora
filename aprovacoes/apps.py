# aprovacoes/apps.py
from django.apps import AppConfig


class AprovacoesConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "aprovacoes"  # CORRETO
    verbose_name = "Aprovações"  # CORRETO

# sst/apps.py
from django.apps import AppConfig


class SstConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "sst"  # CORRETO
    verbose_name = "Saúde e Segurança do Trabalho"  # CORRETO

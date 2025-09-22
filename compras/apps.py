# compras/apps.py
from django.apps import AppConfig


class ComprasConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "compras"  # CORRETO
    verbose_name = "Compras"  # CORRETO

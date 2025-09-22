# bi/apps.py
from django.apps import AppConfig


class BiConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "bi"  # CORRETO
    verbose_name = "Business Intelligence"  # CORRETO

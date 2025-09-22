# formularios/apps.py
from django.apps import AppConfig


class FormulariosConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "formularios"  # CORRETO
    verbose_name = "Formulários"  # CORRETO

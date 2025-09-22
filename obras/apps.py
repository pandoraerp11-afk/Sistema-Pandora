# obras/apps.py
from django.apps import AppConfig


class ObrasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "obras"
    verbose_name = "Obras"  # O verbose_name do AppConfig pode ser plural

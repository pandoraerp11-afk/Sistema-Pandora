# apropriacao/apps.py
from django.apps import AppConfig


class ApropriacaoConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "apropriacao"  # CORRETO
    verbose_name = "Apropriação"  # CORRETO

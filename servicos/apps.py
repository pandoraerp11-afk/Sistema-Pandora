# servicos/apps.py
from django.apps import AppConfig


class ServicosConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "servicos"  # CORRETO
    verbose_name = "Serviços"  # CORRETO

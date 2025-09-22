# treinamento/apps.py
from django.apps import AppConfig


class TreinamentoConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "treinamento"  # CORRETO
    verbose_name = "Treinamento"  # CORRETO

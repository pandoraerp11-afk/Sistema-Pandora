# mao_obra/apps.py
from django.apps import AppConfig


class MaoObraConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "mao_obra"  # CORRETO
    verbose_name = "Mão de Obra"  # CORRETO

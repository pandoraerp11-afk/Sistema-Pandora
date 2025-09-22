# admin/apps.py
from django.apps import AppConfig


class AdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Usar nome de app não conflitante com django.contrib.admin
    name = "admin"  # caminho do módulo interno
    label = "pandora_admin"  # label persistente usado nas migrações existentes
    verbose_name = "Administração"

    def ready(self):
        pass

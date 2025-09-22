# fornecedores/apps.py
from django.apps import AppConfig


class FornecedoresConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "fornecedores"  # CORRETO
    verbose_name = "Fornecedores"  # CORRETO

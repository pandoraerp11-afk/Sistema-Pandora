# funcionarios/apps.py

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FuncionariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "funcionarios"
    verbose_name = _("Funcionários")

    def ready(self):
        pass

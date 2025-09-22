from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AiAuditorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_auditor"
    verbose_name = _("Agente de IA Auditoria")

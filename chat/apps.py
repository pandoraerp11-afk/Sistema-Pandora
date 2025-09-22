# chat/apps.py
from django.apps import AppConfig


class ChatConfig(AppConfig):  # CORRETO
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"  # CORRETO
    verbose_name = "Chat"  # CORRETO

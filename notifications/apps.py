"""Configuração do aplicativo de notificações.

Importa os sinais no momento em que o app é inicializado para garantir
o registro dos receivers (chat, agenda, etc.) durante os testes e execução.
"""

import logging  # noqa: I001 - ordem intencional (logging antes de django)
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuração do app de notificações."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Sistema de Notificações"

    def ready(self) -> None:
        """Executado quando o app está pronto."""
        # Import tardio para registrar receivers de signals (chat, agenda, etc.)
        try:  # pragma: no cover - simples side-effect
            from . import signals  # noqa: F401, PLC0415  # import side-effect dentro de ready é intencional
        except ImportError as e:  # pragma: no cover
            logging.getLogger(__name__).warning(
                "[notifications.apps] Falha ao registrar signals (ImportError): %s",
                e,
            )

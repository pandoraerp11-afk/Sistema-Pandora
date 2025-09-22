"""Stub legado de services do módulo notifications.

Este arquivo substitui o antigo services.py que referenciava modelos
não existentes (NotificationRecipient, NotificationTemplate, etc.).
Mantemos funções NO-OP para evitar import errors caso algum ponto do
código ainda tente importar.

Plano futuro: Implementar engine avançada ou remover completamente.
"""

import logging

logger = logging.getLogger(__name__)


class LegacyNotificationService:
    @staticmethod
    def create_notification(*args, **kwargs):
        logger.warning("[LegacyNotificationService] create_notification chamado - engine avançada inativa.")

    @staticmethod
    def process_notification_rules(*args, **kwargs):
        logger.warning("[LegacyNotificationService] process_notification_rules chamado - engine avançada inativa.")
        return 0


class LegacyNotificationEventEmitter:
    @staticmethod
    def emit_event(*args, **kwargs):
        logger.warning("[LegacyNotificationEventEmitter] emit_event chamado - engine avançada inativa.")


# Funções de conveniência legado
legacy_create_notification = LegacyNotificationService.create_notification
legacy_emit_event = LegacyNotificationEventEmitter.emit_event

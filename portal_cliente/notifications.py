"""Stubs de notificações do Portal Cliente.

Substituir futuramente por integração com canal real (e-mail, fila, etc.).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notificar_agendamento_criado(agendamento) -> None:  # noqa: ANN001 - dinâmica
    """Stub: loga evento de criação de agendamento pelo portal."""
    logger.info(
        "[PortalCliente][Notify] Agendamento criado id=%s cliente=%s profissional=%s",
        agendamento.id,
        agendamento.cliente_id,
        agendamento.profissional_id,
    )


def notificar_agendamento_cancelado(agendamento) -> None:  # noqa: ANN001 - dinâmica
    """Stub: loga evento de cancelamento de agendamento."""
    logger.info(
        "[PortalCliente][Notify] Agendamento cancelado id=%s cliente=%s profissional=%s",
        agendamento.id,
        agendamento.cliente_id,
        agendamento.profissional_id,
    )

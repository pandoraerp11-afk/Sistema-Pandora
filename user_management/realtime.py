"""Utilidades para broadcast de eventos de sessão via Channels."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .risk import compute_risks, session_to_dict


def broadcast_session_event(event, sessao):
    """Envia evento para grupo de monitoramento de sessões."""
    try:
        layer = get_channel_layer()
        if not layer:
            return
        payload = {
            "type": "session.message",
            "event": event,
            "session": session_to_dict(sessao, compute_risks(sessao)),
        }
        async_to_sync(layer.group_send)("sessions_monitor", payload)
    except Exception:
        # Silencia para não quebrar fluxo principal
        pass

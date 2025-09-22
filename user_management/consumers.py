import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .risk import build_context_maps, compute_risks, session_to_dict


class SessionsConsumer(AsyncWebsocketConsumer):
    """WebSocket para atualização em tempo real das sessões de usuários.

    Grupo único (sessions_monitor) por enquanto. Filtros (busca, tenant) são aplicados no cliente.
    """

    group_name = "sessions_monitor"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            # Aceita somente autenticados para evitar exposição indevida
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_initial_snapshot()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            data = {}
        action = data.get("action") or data.get("type")
        if action == "refresh":
            await self.send_initial_snapshot()

    async def send_initial_snapshot(self):
        # Limitar a 50 para não sobrecarregar
        sessoes = await self._recent_sessions(limit=50)
        await self.send(
            text_data=json.dumps(
                {
                    "type": "sessions_snapshot",
                    "timestamp": timezone.now().isoformat(),
                    "sessions": sessoes,
                }
            )
        )

    async def session_message(self, event):  # channel layer -> websocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "session_update",
                    "event": event.get("event"),
                    "session": event.get("session"),
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    # DB helpers
    @database_sync_to_async
    def _recent_sessions(self, limit=50):
        from .models import SessaoUsuario

        qs = list(SessaoUsuario.objects.filter(ativa=True).select_related("user").order_by("-ultima_atividade")[:limit])
        ips_map, paises_map = build_context_maps(qs)
        return [session_to_dict(s, compute_risks(s, ips_map, paises_map)) for s in qs]

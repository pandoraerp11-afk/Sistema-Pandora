# core/consumers.py
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Consumidor WebSocket para atualizações em tempo real do dashboard
    """

    async def connect(self):
        """Conecta ao WebSocket"""
        self.user = self.scope["user"]

        # Comentado para permitir a conexão inicial antes da autenticação completa
        # if not self.user.is_authenticated:
        #     await self.close()
        #     return

        self.room_name = "dashboard"
        self.room_group_name = f"dashboard_{self.room_name}"

        # Juntar ao grupo do dashboard
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Aceitar conexão
        await self.accept()

        # Enviar dados iniciais se o usuário estiver autenticado
        if self.user.is_authenticated:
            await self.send_dashboard_data()

    async def disconnect(self, close_code):
        """Desconecta do WebSocket"""
        # Sair do grupo do dashboard
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Recebe dados do WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get("type")

            if message_type == "request_update":
                await self.send_dashboard_data()
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong", "timestamp": timezone.now().isoformat()}))
        except json.JSONDecodeError:
            pass

    async def send_dashboard_data(self):
        """Envia dados do dashboard"""
        try:
            # Obter dados do dashboard
            dashboard_data = await self.get_dashboard_data()

            # Enviar dados
            await self.send(
                text_data=json.dumps(
                    {"type": "dashboard_update", "data": dashboard_data, "timestamp": timezone.now().isoformat()}
                )
            )
        except Exception as e:
            await self.send(
                text_data=json.dumps({"type": "error", "message": str(e), "timestamp": timezone.now().isoformat()})
            )

    @database_sync_to_async
    def get_dashboard_data(self):
        """Obtém dados do dashboard (versão assíncrona)"""
        try:
            # Importar modelos necessários
            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Dados básicos
            data = {
                "total_users": User.objects.count(),
                "users_online": User.objects.filter(
                    last_login__gte=timezone.now().replace(hour=0, minute=0, second=0)
                ).count(),
                "system_status": "online",
                "last_update": timezone.now().isoformat(),
                "metrics": {"cpu_usage": 45.2, "memory_usage": 67.8, "disk_usage": 23.4, "network_usage": 12.1},
            }

            return data
        except Exception as e:
            return {"error": str(e), "timestamp": timezone.now().isoformat()}

    # Métodos para receber mensagens do grupo
    async def dashboard_update(self, event):
        """Envia atualização do dashboard"""
        await self.send(text_data=json.dumps(event))

    async def notification_update(self, event):
        """Envia atualização de notificação"""
        await self.send(text_data=json.dumps(event))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumidor WebSocket para notificações em tempo real
    Estendido para integrar com modelo Notification atual.
    """

    async def connect(self):
        if self.scope["user"] == AnonymousUser() or not self.scope["user"].is_authenticated:
            await self.close()
            return
        self.user = self.scope["user"]
        # Grupos legacy e novo
        self.primary_group = f"notifications_{self.user.id}"  # legado
        self.alt_group = f"notif_user_{self.user.id}"  # usado pelos signals recentes
        await self.channel_layer.group_add(self.primary_group, self.channel_name)
        await self.channel_layer.group_add(self.alt_group, self.channel_name)
        await self.accept()
        await self._send_snapshot()

    async def disconnect(self, close_code):
        if hasattr(self, "primary_group"):
            await self.channel_layer.group_discard(self.primary_group, self.channel_name)
        if hasattr(self, "alt_group"):
            await self.channel_layer.group_discard(self.alt_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        action = data.get("type") or data.get("action")
        if action == "mark_read":
            nid = data.get("notification_id")
            if nid:
                updated = await self._mark_read(nid)
                if updated:
                    count = await self._unread_count()
                    payload = {
                        "type": "notifications_update",
                        "event": "marked_read",
                        "notification_id": nid,
                        "unread_count": count,
                    }
                    # Broadcast para ambos grupos
                    await self.channel_layer.group_send(self.primary_group, payload)
                    await self.channel_layer.group_send(self.alt_group, payload)
        elif action == "mark_read_bulk":
            ids = data.get("ids") or []
            if ids:
                changed = 0
                for nid in ids:
                    ch = await self._mark_read(nid)
                    changed += 1 if ch else 0
                if changed:
                    count = await self._unread_count()
                    payload = {
                        "type": "notifications_update",
                        "event": "marked_read_bulk",
                        "ids": ids,
                        "unread_count": count,
                    }
                    await self.channel_layer.group_send(self.primary_group, payload)
                    await self.channel_layer.group_send(self.alt_group, payload)
        elif action == "refresh":
            await self._send_snapshot()

    async def _send_snapshot(self):
        notifications = await self._recent_unread()
        count = await self._unread_count()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notifications_snapshot",
                    "unread_count": count,
                    "notifications": notifications,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    # Métodos chamados via channel layer
    async def notification_message(self, event):
        # legado
        await self.send(text_data=json.dumps(event))

    async def notifications_update(self, event):
        # Novo formato vindo do signal (type: notifications.update -> notifications_update)
        await self.send(text_data=json.dumps(event))

    # DB helpers
    @database_sync_to_async
    def _recent_unread(self, limit=10):
        try:
            from notifications.models import Notification

            qs = Notification.objects.filter(usuario_destinatario=self.user, status="nao_lida").order_by("-created_at")[
                :limit
            ]
            return [
                {
                    "id": n.id,
                    "titulo": n.titulo,
                    "mensagem": n.mensagem[:120] + ("..." if len(n.mensagem) > 120 else ""),
                    "tipo": n.tipo,
                    "prioridade": n.prioridade,
                    "created_at": n.created_at.isoformat(),
                    "url_acao": n.url_acao,
                }
                for n in qs
            ]
        except Exception:
            return []

    @database_sync_to_async
    def _unread_count(self):
        try:
            from notifications.models import Notification

            return Notification.objects.filter(usuario_destinatario=self.user, status="nao_lida").count()
        except Exception:
            return 0

    @database_sync_to_async
    def _mark_read(self, notification_id):
        try:
            from notifications.models import Notification

            n = Notification.objects.get(id=notification_id, usuario_destinatario=self.user)
            if n.status == "nao_lida":
                n.marcar_como_lida()
                return True
            return False
        except Exception:
            return False

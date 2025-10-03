# core/consumers.py
"""Consumidores WebSocket para atualizações em tempo real do painel e de notificações."""

from __future__ import annotations

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.utils import timezone

from notifications.models import Notification

logger = logging.getLogger(__name__)

NOTIFICATION_PREVIEW_LENGTH = 120


class DashboardConsumer(AsyncWebsocketConsumer):
    """Consumidor WebSocket para atualizações em tempo real do dashboard."""

    async def connect(self) -> None:
        """Conecta ao WebSocket, autentica e junta-se ao grupo do dashboard."""
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.room_name = "dashboard"
        self.room_group_name = f"dashboard_{self.room_name}"

        # Juntar ao grupo do dashboard
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Aceitar conexão
        await self.accept()

        # Enviar dados iniciais
        await self.send_dashboard_data()

    async def disconnect(self, _close_code: int | None = None) -> None:
        """Desconecta do WebSocket e sai do grupo do dashboard."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data: str) -> None:
        """Recebe dados do WebSocket para solicitar atualizações ou para pings."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get("type")

            if message_type == "request_update":
                await self.send_dashboard_data()
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong", "timestamp": timezone.now().isoformat()}))
        except json.JSONDecodeError:
            logger.warning("Recebida uma mensagem JSON inválida no DashboardConsumer.")

    async def send_dashboard_data(self) -> None:
        """Busca e envia os dados mais recentes do dashboard para o cliente."""
        try:
            dashboard_data = await self.get_dashboard_data()
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "dashboard_update",
                        "data": dashboard_data,
                        "timestamp": timezone.now().isoformat(),
                    },
                ),
            )
        except Exception as e:
            logger.exception("Erro ao enviar dados do dashboard.")
            await self.send(
                text_data=json.dumps({"type": "error", "message": str(e), "timestamp": timezone.now().isoformat()}),
            )

    @database_sync_to_async
    def get_dashboard_data(self) -> dict[str, Any]:
        """Obtém dados do dashboard de forma assíncrona a partir do banco de dados."""
        user_model = get_user_model()
        try:
            return {
                "total_users": user_model.objects.count(),
                "users_online": user_model.objects.filter(
                    last_login__gte=timezone.now().replace(hour=0, minute=0, second=0),
                ).count(),
                "system_status": "online",
                "last_update": timezone.now().isoformat(),
                "metrics": {"cpu_usage": 45.2, "memory_usage": 67.8, "disk_usage": 23.4, "network_usage": 12.1},
            }
        except Exception as e:
            logger.exception("Erro ao buscar dados do dashboard no banco de dados.")
            return {"error": str(e), "timestamp": timezone.now().isoformat()}

    async def dashboard_update(self, event: dict[str, Any]) -> None:
        """Envia uma atualização do dashboard recebida do grupo de canais."""
        await self.send(text_data=json.dumps(event))

    async def notification_update(self, event: dict[str, Any]) -> None:
        """Envia uma atualização de notificação recebida do grupo de canais."""
        await self.send(text_data=json.dumps(event))


class NotificationConsumer(AsyncWebsocketConsumer):
    """Consumidor WebSocket para notificações em tempo real.

    Este consumidor lida com a conexão de usuários autenticados,
    envia um snapshot inicial de notificações não lidas e processa
    ações como marcar notificações como lidas.
    """

    user: AbstractBaseUser | AnonymousUser

    async def connect(self) -> None:
        """Gerencia a conexão do cliente, autentica e junta-se aos grupos de notificação."""
        self.user = self.scope.get("user", AnonymousUser())

        if not self.user.is_authenticated:
            await self.close()
            return

        self.primary_group = f"notifications_{self.user.id}"
        self.alt_group = f"notif_user_{self.user.id}"
        await self.channel_layer.group_add(self.primary_group, self.channel_name)
        await self.channel_layer.group_add(self.alt_group, self.channel_name)
        await self.accept()
        await self._send_snapshot()

    async def disconnect(self, _close_code: int | None = None) -> None:
        """Desconecta o cliente e o remove dos grupos de notificação."""
        if hasattr(self, "primary_group"):
            await self.channel_layer.group_discard(self.primary_group, self.channel_name)
        if hasattr(self, "alt_group"):
            await self.channel_layer.group_discard(self.alt_group, self.channel_name)

    async def receive(self, text_data: str) -> None:
        """Recebe e processa ações do cliente, como marcar notificações como lidas."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.warning("Recebida uma mensagem JSON inválida no NotificationConsumer.")
            return

        action = data.get("type") or data.get("action")
        if action == "mark_read":
            await self._handle_mark_read(data)
        elif action == "mark_read_bulk":
            await self._handle_mark_read_bulk(data)
        elif action == "refresh":
            await self._send_snapshot()

    async def _handle_mark_read(self, data: dict[str, Any]) -> None:
        """Lida com a ação de marcar uma única notificação como lida."""
        nid = data.get("notification_id")
        if not nid:
            return

        if await self._mark_read(nid):
            count = await self._unread_count()
            payload = {
                "type": "notifications_update",
                "event": "marked_read",
                "notification_id": nid,
                "unread_count": count,
            }
            await self.channel_layer.group_send(self.primary_group, payload)
            await self.channel_layer.group_send(self.alt_group, payload)

    async def _handle_mark_read_bulk(self, data: dict[str, Any]) -> None:
        """Lida com a ação de marcar múltiplas notificações como lidas."""
        ids = data.get("ids", [])
        if not ids:
            return

        changed = 0
        for nid in ids:
            if await self._mark_read(nid):
                changed += 1

        if changed > 0:
            count = await self._unread_count()
            payload = {
                "type": "notifications_update",
                "event": "marked_read_bulk",
                "ids": ids,
                "unread_count": count,
            }
            await self.channel_layer.group_send(self.primary_group, payload)
            await self.channel_layer.group_send(self.alt_group, payload)

    async def _send_snapshot(self) -> None:
        """Envia um snapshot inicial com as notificações recentes e a contagem de não lidas."""
        notifications = await self._recent_unread()
        count = await self._unread_count()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notifications_snapshot",
                    "unread_count": count,
                    "notifications": notifications,
                    "timestamp": timezone.now().isoformat(),
                },
            ),
        )

    async def notification_message(self, event: dict[str, Any]) -> None:
        """Manipulador para mensagens de notificação (formato legado)."""
        await self.send(text_data=json.dumps(event))

    async def notifications_update(self, event: dict[str, Any]) -> None:
        """Manipulador para atualizações de notificação (novo formato vindo do signal)."""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _recent_unread(self, limit: int = 10) -> list[dict[str, Any]]:
        """Busca as notificações não lidas mais recentes para o usuário."""
        try:
            qs = Notification.objects.filter(usuario_destinatario=self.user, status="nao_lida").order_by("-created_at")[
                :limit
            ]
            return [
                {
                    "id": n.id,
                    "titulo": n.titulo,
                    "mensagem": (
                        f"{n.mensagem[:NOTIFICATION_PREVIEW_LENGTH]}..."
                        if len(n.mensagem) > NOTIFICATION_PREVIEW_LENGTH
                        else n.mensagem
                    ),
                    "tipo": n.tipo,
                    "prioridade": n.prioridade,
                    "created_at": n.created_at.isoformat(),
                    "url_acao": n.url_acao,
                }
                for n in qs
            ]
        except Exception:
            logger.exception("Erro ao buscar notificações recentes não lidas.")
            return []

    @database_sync_to_async
    def _unread_count(self) -> int:
        """Conta o número total de notificações não lidas para o usuário."""
        try:
            return Notification.objects.filter(usuario_destinatario=self.user, status="nao_lida").count()
        except Exception:
            logger.exception("Erro ao contar notificações não lidas.")
            return 0

    @database_sync_to_async
    def _mark_read(self, notification_id: int) -> bool:
        """Marca uma notificação específica como lida."""
        try:
            notification = Notification.objects.get(id=notification_id, usuario_destinatario=self.user)
            if notification.status == "nao_lida":
                notification.marcar_como_lida()
                return True
        except Notification.DoesNotExist:
            logger.warning("Tentativa de marcar notificação inexistente %s como lida.", notification_id)
        except Exception:
            logger.exception("Erro ao marcar notificação %s como lida.", notification_id)
        return False

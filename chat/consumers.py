import asyncio
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Count
from django.utils import timezone

from .models import Conversa, LogMensagem, Mensagem

# Presença global simples (para produção usar Redis ou cache compartilhado)
GLOBAL_PRESENCE = {}  # fallback in-memory

# Armazenamento de presença simples em memória (para produção usar Redis / cache compartilhado)
PRESENCA_CONVERSA = {}  # fallback in-memory

REDIS_ENABLED = False
try:
    from django.conf import settings

    if settings.CHANNEL_LAYERS["default"]["BACKEND"].endswith("RedisChannelLayer"):
        REDIS_ENABLED = True
except Exception:
    pass


async def redis_set_presence(channel_layer, key, user_id):
    try:
        conn = await channel_layer._get_connection()  # type: ignore (private API)
        await conn.execute_command("HSET", key, user_id, int(timezone.now().timestamp()))
        await conn.execute_command("EXPIRE", key, 180)
    except Exception:
        pass


async def redis_remove_presence(channel_layer, key, user_id):
    try:
        conn = await channel_layer._get_connection()
        await conn.execute_command("HDEL", key, user_id)
    except Exception:
        pass


async def redis_list_presence(channel_layer, key, max_age=120):
    try:
        conn = await channel_layer._get_connection()
        data = await conn.execute_command("HGETALL", key)
        # data is list [field, value, field, value, ...]
        agora = timezone.now().timestamp()
        result = []
        for i in range(0, len(data), 2):
            uid = int(data[i])
            ts = float(data[i + 1])
            if (agora - ts) <= max_age:
                result.append(uid)
        return result
    except Exception:
        return []


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer WebSocket para mensagens em tempo real de uma conversa específica."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or user == AnonymousUser() or not user.is_authenticated:
            await self.close()
            return

        self.conversa_id = self.scope["url_route"]["kwargs"].get("conversa_id")
        self.group_name = f"chat_conversa_{self.conversa_id}"

        # Validar participação
        if not await self.user_in_conversa(user.id, self.conversa_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Atualizar presença
        await self._mark_presence(user.id)
        await self._broadcast_presence()
        await self._mark_global_presence(user.id)
        await self._broadcast_global_presence()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        user = self.scope.get("user")
        if user and user.is_authenticated:
            await self._remove_presence(user.id)
            await self._broadcast_presence()
            await self._remove_global_presence(user.id)
            await self._broadcast_global_presence()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action")
        user = self.scope["user"]

        if action == "send_message":
            conteudo = (data.get("conteudo") or "").strip()
            if conteudo:
                mensagem = await self._criar_mensagem(user.id, self.conversa_id, conteudo)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "chat.message",
                        "event": "new_message",
                        "mensagem": mensagem,
                    },
                )
                # Tentar marcar como entregue se há outros presentes
                delivered_to = await self._marcar_entregue_if_online(mensagem["id"])
                if delivered_to:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "chat.status",
                            "event": "message_status",
                            "message_id": mensagem["id"],
                            "status": "entregue",
                        },
                    )
                # Notificar visão geral (unread counters) para todos participantes
                participantes = await self._obter_participantes_ids(self.conversa_id)
                for pid in participantes:
                    await self.channel_layer.group_send(
                        f"chat_user_{pid}",
                        {
                            "type": "chat.overview",
                            "event": "conversation_activity",
                            "conversa_id": int(self.conversa_id),
                            "origin_user_id": user.id,
                        },
                    )
        elif action == "mark_read":
            ids = data.get("message_ids") or []
            if ids:
                updated = await self._marcar_lidas(user.id, self.conversa_id, ids)
                if updated:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {"type": "chat.read", "event": "messages_read", "user_id": user.id, "message_ids": updated},
                    )
                    # Atualizar status para "lida"
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "chat.status",
                            "event": "messages_status_bulk",
                            "message_ids": updated,
                            "status": "lida",
                        },
                    )
        elif action == "edit_message":
            msg_id = data.get("message_id")
            novo = (data.get("conteudo") or "").strip()
            if msg_id and novo:
                msg_dict = await self._editar_mensagem(user.id, self.conversa_id, msg_id, novo)
                if msg_dict:
                    await self.channel_layer.group_send(
                        self.group_name, {"type": "chat.message", "event": "message_edited", "mensagem": msg_dict}
                    )
        elif action == "delete_message":
            msg_id = data.get("message_id")
            if msg_id:
                deleted = await self._excluir_mensagem(user.id, self.conversa_id, msg_id)
                if deleted:
                    await self.channel_layer.group_send(
                        self.group_name, {"type": "chat.message", "event": "message_deleted", "message_id": msg_id}
                    )
        elif action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "event": "typing",
                    "user_id": user.id,
                    "username": user.username,
                },
            )
        elif action == "ping":
            await self._mark_presence(user.id)
            await self._broadcast_presence(single=False)
            await self._mark_global_presence(user.id)
            await self._broadcast_global_presence()
        elif action == "reaction":
            msg_id = data.get("message_id")
            emoji = data.get("emoji")
            if msg_id and emoji:
                reacoes = await self._toggle_reacao(user.id, self.conversa_id, msg_id, emoji)
                if reacoes is not None:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "chat.message",
                            "event": "message_reactions",
                            "message_id": msg_id,
                            "reacoes": reacoes,
                        },
                    )
        elif action == "pin":
            msg_id = data.get("message_id")
            if msg_id:
                fixada = await self._toggle_pin(user.id, self.conversa_id, msg_id)
                if fixada is not None:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {"type": "chat.message", "event": "message_pinned", "message_id": msg_id, "fixada": fixada},
                    )

    # Eventos enviados ao grupo
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_typing(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_presence(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_read(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_status(self, event):
        await self.send(text_data=json.dumps(event))

    # Helpers de presença
    async def _mark_presence(self, user_id):
        if REDIS_ENABLED:
            await redis_set_presence(self.channel_layer, f"chat:conv:{self.conversa_id}:presence", user_id)
        else:
            users = PRESENCA_CONVERSA.setdefault(int(self.conversa_id), {})
            users[user_id] = timezone.now().timestamp()

    async def _remove_presence(self, user_id):
        if REDIS_ENABLED:
            await redis_remove_presence(self.channel_layer, f"chat:conv:{self.conversa_id}:presence", user_id)
        else:
            users = PRESENCA_CONVERSA.get(int(self.conversa_id), {})
            if user_id in users:
                del users[user_id]

    async def _broadcast_presence(self, single=False):
        if REDIS_ENABLED:
            online_ids = await redis_list_presence(
                self.channel_layer, f"chat:conv:{self.conversa_id}:presence", max_age=90
            )
        else:
            users = PRESENCA_CONVERSA.get(int(self.conversa_id), {})
            agora = timezone.now().timestamp()
            inativos = [uid for uid, ts in users.items() if (agora - ts) > 60]
            for uid in inativos:
                del users[uid]
            online_ids = list(users.keys())
        await self.channel_layer.group_send(
            self.group_name, {"type": "chat.presence", "event": "presence", "online_user_ids": online_ids}
        )

    # Presença global
    async def _mark_global_presence(self, user_id):
        if REDIS_ENABLED:
            await redis_set_presence(self.channel_layer, "chat:global:presence", user_id)
        else:
            GLOBAL_PRESENCE[user_id] = timezone.now().timestamp()

    async def _remove_global_presence(self, user_id):
        if REDIS_ENABLED:
            await redis_remove_presence(self.channel_layer, "chat:global:presence", user_id)
        elif user_id in GLOBAL_PRESENCE:
            del GLOBAL_PRESENCE[user_id]

    async def _broadcast_global_presence(self):
        if REDIS_ENABLED:
            online_ids = await redis_list_presence(self.channel_layer, "chat:global:presence", max_age=150)
        else:
            agora = timezone.now().timestamp()
            for uid, ts in list(GLOBAL_PRESENCE.items()):
                if (agora - ts) > 120:
                    del GLOBAL_PRESENCE[uid]
            online_ids = list(GLOBAL_PRESENCE.keys())
        # Notificar todos participantes desta conversa (apenas aqueles com overview socket)
        participantes = await self._obter_participantes_ids(self.conversa_id)
        for pid in participantes:
            await self.channel_layer.group_send(
                f"chat_user_{pid}", {"type": "chat.overview", "event": "presence_update", "online_user_ids": online_ids}
            )

    # Acesso ao banco (sync -> async)
    @database_sync_to_async
    def user_in_conversa(self, user_id, conversa_id):
        try:
            return Conversa.objects.filter(id=conversa_id, participantes__id=user_id).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _criar_mensagem(self, user_id, conversa_id, conteudo):
        try:
            conversa = Conversa.objects.get(id=conversa_id)
            user = conversa.participantes.get(id=user_id)
            mensagem = Mensagem.objects.create(
                tenant=conversa.tenant, conversa=conversa, remetente=user, conteudo=conteudo, tipo="texto"
            )
            conversa.ultima_atividade = timezone.now()
            conversa.save(update_fields=["ultima_atividade"])
            LogMensagem.objects.create(mensagem=mensagem, usuario=user, acao="Mensagem enviada via WS")
            return {
                "id": mensagem.id,
                "conteudo": mensagem.conteudo,
                "remetente": mensagem.remetente.username,
                "remetente_id": mensagem.remetente.id,
                "created_at": mensagem.created_at.isoformat(),
                "status": mensagem.status,
            }
        except Exception:
            return {"erro": "nao_criada"}

    @database_sync_to_async
    def _obter_participantes_ids(self, conversa_id):
        try:
            return list(Conversa.objects.get(id=conversa_id).participantes.values_list("id", flat=True))
        except Exception:
            return []

    @database_sync_to_async
    def _marcar_lidas(self, user_id, conversa_id, ids):
        try:
            qs = Mensagem.objects.filter(conversa_id=conversa_id, id__in=ids).exclude(remetente_id=user_id)
            atualizadas = list(qs.values_list("id", flat=True))
            qs.update(lida=True, status="lida", data_leitura=timezone.now())
            # Sincronizar notificações (import local para evitar ciclo)
            if atualizadas:
                try:
                    from django.contrib.auth import get_user_model

                    from notifications.views import marcar_notificacoes_chat_lidas

                    User = get_user_model()
                    usuario = User.objects.get(id=user_id)
                    marcar_notificacoes_chat_lidas(conversa_id, usuario, mensagem_ids=atualizadas)
                except Exception:
                    pass
            return atualizadas
        except Exception:
            return []

    @database_sync_to_async
    def _editar_mensagem(self, user_id, conversa_id, msg_id, novo):
        try:
            msg = Mensagem.objects.get(
                id=msg_id,
                conversa_id=conversa_id,
                remetente_id=user_id,
                status__in=["enviada", "entregue", "editada", "lida"],
            )
            msg.conteudo = novo
            msg.status = "editada"
            msg.data_edicao = timezone.now()
            msg.save(update_fields=["conteudo", "status", "data_edicao"])
            LogMensagem.objects.create(mensagem=msg, usuario=msg.remetente, acao="Mensagem editada via WS")
            return {
                "id": msg.id,
                "conteudo": msg.conteudo,
                "remetente": msg.remetente.username,
                "remetente_id": msg.remetente.id,
                "created_at": msg.created_at.isoformat(),
                "status": msg.status,
                "edited": True,
            }
        except Exception:
            return None

    @database_sync_to_async
    def _excluir_mensagem(self, user_id, conversa_id, msg_id):
        try:
            msg = Mensagem.objects.get(id=msg_id, conversa_id=conversa_id, remetente_id=user_id)
            msg.status = "excluida"
            msg.conteudo = "[Mensagem excluída]"
            msg.save(update_fields=["status", "conteudo"])
            LogMensagem.objects.create(mensagem=msg, usuario=msg.remetente, acao="Mensagem excluída via WS")
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _marcar_entregue_if_online(self, mensagem_id):
        try:
            msg = Mensagem.objects.get(id=mensagem_id)
            # Se houver pelo menos um outro participante online na conversa, marcar entregue
            online_ids = list(PRESENCA_CONVERSA.get(msg.conversa_id, {}).keys())
            if any(uid != msg.remetente_id for uid in online_ids):
                if msg.status == "enviada":
                    msg.status = "entregue"
                    msg.save(update_fields=["status"])
                return [uid for uid in online_ids if uid != msg.remetente_id]
            return []
        except Exception:
            return []

    @database_sync_to_async
    def _toggle_reacao(self, user_id, conversa_id, msg_id, emoji):
        from .models import MensagemReacao

        try:
            msg = Mensagem.objects.get(id=msg_id, conversa_id=conversa_id)
            r, created = MensagemReacao.objects.get_or_create(mensagem=msg, usuario_id=user_id, emoji=emoji[:32])
            if not created:
                r.delete()
            return list(msg.reacoes.values("emoji").annotate(total=Count("emoji")).order_by("-total"))
        except Exception:
            return None

    @database_sync_to_async
    def _toggle_pin(self, user_id, conversa_id, msg_id):
        from .models import MensagemFixada

        try:
            msg = Mensagem.objects.get(id=msg_id, conversa_id=conversa_id)
            fix, created = MensagemFixada.objects.get_or_create(
                conversa_id=conversa_id, mensagem=msg, defaults={"fixada_por_id": user_id}
            )
            if not created:
                fix.delete()
                return False
            return True
        except Exception:
            return None


class ChatOverviewConsumer(AsyncWebsocketConsumer):
    """Consumer para atualizar contadores de conversas (lista/home) em tempo real."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.group_name = f"chat_user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Enviar snapshot inicial
        snapshot = await self._snapshot(user.id)
        await self.send(
            text_data=json.dumps(
                {"event": "snapshot", "conversas": snapshot, "online_user_ids": self._global_online_ids()}
            )
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Permitir requisição manual de atualização
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get("action") == "refresh":
                    user = self.scope["user"]
                    snapshot = await self._snapshot(user.id)
                    await self.send(text_data=json.dumps({"event": "snapshot", "conversas": snapshot}))
            except Exception:
                pass

    async def chat_overview(self, event):
        # Evento vindo de ChatConsumer
        user = self.scope["user"]
        snapshot = await self._snapshot(user.id, conversa_id=event.get("conversa_id"))
        if event.get("event") == "presence_update":
            await self.send(
                text_data=json.dumps({"event": "presence_update", "online_user_ids": event.get("online_user_ids", [])})
            )
        else:
            await self.send(text_data=json.dumps({"event": "conversation_activity", "conversas": snapshot}))

    @database_sync_to_async
    def _snapshot(self, user_id, conversa_id=None):
        try:
            qs = Conversa.objects.filter(participantes__id=user_id, status="ativa")
            if conversa_id:
                qs = qs.filter(id=conversa_id)
            data = []
            for c in qs:
                unread = c.mensagens.filter(lida=False).exclude(remetente_id=user_id).count()
                data.append(
                    {
                        "id": c.id,
                        "unread": unread,
                        "ultima_atividade": c.ultima_atividade.isoformat() if c.ultima_atividade else None,
                    }
                )
            return data
        except Exception:
            return []

    def _global_online_ids(self):
        if REDIS_ENABLED:
            # Não async aqui; para simplicidade retorna cache in-memory se Redis (poderia ser melhorado)
            # Poderíamos transformar em async e chamar redis_list_presence via loop.
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(redis_list_presence(get_channel_layer(), "chat:global:presence", 150))  # type: ignore
            except Exception:
                pass
        agora = timezone.now().timestamp()
        for uid, ts in list(GLOBAL_PRESENCE.items()):
            if (agora - ts) > 120:
                del GLOBAL_PRESENCE[uid]
        return list(GLOBAL_PRESENCE.keys())

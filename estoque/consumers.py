"""
Consumidores WebSocket para Eventos de Estoque em Tempo Real
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class EstoqueStreamConsumer(AsyncJsonWebsocketConsumer):
    """Consumer aprimorado para eventos gerais de estoque"""

    async def connect(self):
        """Conectar ao stream de estoque com validações"""
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close()
            return

        self.user = user
        tenant_id = self.scope["url_route"]["kwargs"].get("tenant_id") if "url_route" in self.scope else None

        # Grupos básicos
        self._groups = ["estoque_stream"]
        if tenant_id:
            self._groups.append(f"estoque_tenant_{tenant_id}")

        # Adicionar grupo específico do usuário se for separador
        if await self.user_is_separador():
            self._groups.append(f"estoque_user_{user.id}")

        for g in self._groups:
            await self.channel_layer.group_add(g, self.channel_name)

        await self.accept()
        await self.send_json(
            {
                "event": "connection",
                "status": "ok",
                "groups": self._groups,
                "user": user.get_full_name(),
                "permissions": await self.get_user_permissions(),
            }
        )

    async def disconnect(self, code):
        """Desconectar dos grupos"""
        for g in getattr(self, "_groups", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Receber mensagens do cliente"""
        action = content.get("action")

        if action == "ping":
            await self.send_json({"event": "pong", "timestamp": await self.get_timestamp()})

        elif action == "subscribe_produto":
            # Inscrever em eventos de produto específico
            produto_id = content.get("produto_id")
            if produto_id and await self.user_can_monitor_produto(produto_id):
                group_name = f"estoque_produto_{produto_id}"
                await self.channel_layer.group_add(group_name, self.channel_name)
                await self.send_json({"event": "subscribed", "produto_id": produto_id})

        elif action == "get_status":
            # Enviar status atual do estoque
            await self.send_status_update()

    async def estoque_event(self, event):
        """Processar evento de estoque com filtros"""
        event_data = event["data"]

        # Verificar se usuário pode receber este evento
        if await self.user_can_receive_event(event_data):
            # Enriquecer evento com informações contextuais
            enhanced_event = event_data.copy()
            enhanced_event["received_at"] = await self.get_timestamp()
            enhanced_event["user_id"] = self.user.id

            await self.send_json(enhanced_event)

    async def send_status_update(self):
        """Enviar atualização de status do estoque"""
        status = await self.get_estoque_status()
        await self.send_json({"event": "status_update", "data": status, "timestamp": await self.get_timestamp()})

    @database_sync_to_async
    def user_is_separador(self):
        """Verificar se usuário é separador"""
        return self.user.groups.filter(name__in=["Separadores", "Estoque"]).exists()

    @database_sync_to_async
    def get_user_permissions(self):
        """Obter permissões do usuário"""
        permissions = []
        if self.user.is_staff:
            permissions.append("admin")
        if self.user.groups.filter(name="Separadores").exists():
            permissions.append("picking")
        if self.user.groups.filter(name="Auditores").exists():
            permissions.append("audit")
        return permissions

    @database_sync_to_async
    def user_can_monitor_produto(self, produto_id):
        """Verificar se usuário pode monitorar produto"""
        # Por enquanto permitir para usuários de estoque
        return self.user.is_staff or self.user.groups.filter(name="Estoque").exists()

    @database_sync_to_async
    def user_can_receive_event(self, event_data):
        """Filtrar eventos baseado em permissões"""
        event_type = event_data.get("event", "")

        # Eventos sensíveis apenas para auditores
        sensitive_events = ["auditoria_", "suspeito_", "alerta_"]
        if any(event_type.startswith(se) for se in sensitive_events):
            return self.user.groups.filter(name="Auditores").exists()

        return True

    @database_sync_to_async
    def get_estoque_status(self):
        """Obter status atual do estoque"""
        from django.db.models import Sum

        from estoque.models import EstoqueSaldo, PedidoSeparacao, ReservaEstoque

        tenant = getattr(self.user, "tenant", None)

        # Estatísticas básicas
        saldos = EstoqueSaldo.objects.all()
        reservas = ReservaEstoque.objects.filter(status="ATIVA")
        pedidos = PedidoSeparacao.objects.filter(status__in=["PENDENTE", "EM_SEPARACAO"])

        if tenant:
            saldos = saldos.filter(tenant=tenant)
            reservas = reservas.filter(tenant=tenant)
            pedidos = pedidos.filter(tenant=tenant)

        return {
            "total_produtos": saldos.count(),
            "total_reservado": float(reservas.aggregate(total=Sum("quantidade"))["total"] or 0),
            "pedidos_pendentes": pedidos.filter(status="PENDENTE").count(),
            "pedidos_em_separacao": pedidos.filter(status="EM_SEPARACAO").count(),
        }

    @database_sync_to_async
    def get_timestamp(self):
        """Obter timestamp atual"""
        from django.utils import timezone

        return timezone.now().isoformat()


class PickingStreamConsumer(AsyncJsonWebsocketConsumer):
    """Consumer aprimorado para eventos de picking"""

    async def connect(self):
        """Conectar ao stream de picking"""
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close()
            return

        # Verificar permissão para picking
        if not await self.user_has_picking_access(user):
            await self.close()
            return

        self.user = user
        tenant_id = self.scope["url_route"]["kwargs"].get("tenant_id") if "url_route" in self.scope else None

        self._groups = ["picking_stream"]
        if tenant_id:
            self._groups.append(f"picking_tenant_{tenant_id}")

        # Grupo específico do usuário
        self._groups.append(f"picking_user_{user.id}")

        for g in self._groups:
            await self.channel_layer.group_add(g, self.channel_name)

        await self.accept()
        await self.send_json(
            {"event": "connection", "status": "ok", "user": user.get_full_name(), "role": await self.get_user_role()}
        )

        # Enviar estado inicial
        await self.send_initial_picking_state()

    async def disconnect(self, code):
        """Desconectar dos grupos"""
        for g in getattr(self, "_groups", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Processar mensagens do cliente"""
        action = content.get("action")

        if action == "ping":
            await self.send_json({"event": "pong"})

        elif action == "subscribe_pedido":
            pedido_id = content.get("pedido_id")
            if pedido_id and await self.user_can_access_pedido(pedido_id):
                group_name = f"picking_pedido_{pedido_id}"
                await self.channel_layer.group_add(group_name, self.channel_name)
                await self.send_json({"event": "subscribed_pedido", "pedido_id": pedido_id})

        elif action == "get_my_pedidos":
            pedidos = await self.get_user_pedidos()
            await self.send_json({"event": "my_pedidos", "data": pedidos})

        elif action == "heartbeat":
            await self.send_json(
                {
                    "event": "heartbeat_response",
                    "timestamp": await self.get_timestamp(),
                    "active_pedidos": await self.count_active_pedidos(),
                }
            )

    async def picking_event(self, event):
        """Processar evento de picking"""
        event_data = event["data"]

        # Enriquecer evento
        enhanced_event = event_data.copy()
        enhanced_event["received_at"] = await self.get_timestamp()

        await self.send_json(enhanced_event)

    async def send_initial_picking_state(self):
        """Enviar estado inicial do picking"""
        state = await self.get_picking_state()
        await self.send_json({"event": "initial_state", "data": state, "timestamp": await self.get_timestamp()})

    @database_sync_to_async
    def user_has_picking_access(self, user):
        """Verificar acesso ao sistema de picking"""
        return user.is_staff or user.groups.filter(name__in=["Separadores", "Estoque", "Conferentes"]).exists()

    @database_sync_to_async
    def get_user_role(self):
        """Obter role do usuário no picking"""
        if self.user.groups.filter(name="Separadores").exists():
            return "separador"
        elif self.user.groups.filter(name="Conferentes").exists():
            return "conferente"
        elif self.user.is_staff:
            return "admin"
        return "viewer"

    @database_sync_to_async
    def user_can_access_pedido(self, pedido_id):
        """Verificar acesso a pedido específico"""
        from estoque.models import PedidoSeparacao

        try:
            pedido = PedidoSeparacao.objects.get(id=pedido_id)
            return (
                self.user in (pedido.separador, pedido.conferente, pedido.criado_por) or self.user.is_staff
            )
        except PedidoSeparacao.DoesNotExist:
            return False

    @database_sync_to_async
    def get_user_pedidos(self):
        """Obter pedidos do usuário"""
        from django.db.models import Q

        from estoque.models import PedidoSeparacao

        queryset = PedidoSeparacao.objects.filter(
            Q(separador=self.user) | Q(conferente=self.user) | Q(status="PENDENTE") | Q(criado_por=self.user)
        ).select_related("criado_por")

        if hasattr(self.user, "tenant"):
            queryset = queryset.filter(tenant=self.user.tenant)

        return list(
            queryset.values(
                "id", "status", "prioridade", "criado_em", "criado_por__first_name", "criado_por__last_name"
            ).order_by("-criado_em")[:20]
        )

    @database_sync_to_async
    def get_picking_state(self):
        """Obter estado do sistema de picking"""
        from django.db.models import Count, Q

        from estoque.models import PedidoSeparacao

        tenant = getattr(self.user, "tenant", None)
        queryset = PedidoSeparacao.objects.all()

        if tenant:
            queryset = queryset.filter(tenant=tenant)

        stats = queryset.aggregate(
            pendentes=Count("id", filter=Q(status="PENDENTE")),
            em_separacao=Count("id", filter=Q(status="EM_SEPARACAO")),
            separados=Count("id", filter=Q(status="SEPARADO")),
            conferidos=Count("id", filter=Q(status="CONFERIDO")),
        )

        # Pedidos do usuário
        meus_pedidos = queryset.filter(separador=self.user).aggregate(
            meus_em_separacao=Count("id", filter=Q(status="EM_SEPARACAO"))
        )

        stats.update(meus_pedidos)
        return stats

    @database_sync_to_async
    def count_active_pedidos(self):
        """Contar pedidos ativos do usuário"""
        from estoque.models import PedidoSeparacao

        return PedidoSeparacao.objects.filter(separador=self.user, status="EM_SEPARACAO").count()

    @database_sync_to_async
    def get_timestamp(self):
        """Obter timestamp atual"""
        from django.utils import timezone

        return timezone.now().isoformat()


class AuditoriaStreamConsumer(AsyncJsonWebsocketConsumer):
    """Consumer para eventos de auditoria"""

    async def connect(self):
        """Conectar ao stream de auditoria"""
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close()
            return

        # Verificar permissão de auditoria
        if not await self.user_is_auditor(user):
            await self.close()
            return

        self.user = user
        tenant_id = self.scope["url_route"]["kwargs"].get("tenant_id") if "url_route" in self.scope else None

        self._groups = ["auditoria_stream"]
        if tenant_id:
            self._groups.append(f"auditoria_tenant_{tenant_id}")

        for g in self._groups:
            await self.channel_layer.group_add(g, self.channel_name)

        await self.accept()
        await self.send_json(
            {
                "event": "auditoria_connected",
                "user": user.get_full_name(),
                "access_level": await self.get_audit_access_level(),
            }
        )

    async def disconnect(self, code):
        """Desconectar dos grupos"""
        for g in getattr(self, "_groups", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Processar mensagens de auditoria"""
        action = content.get("action")

        if action == "ping":
            await self.send_json({"event": "pong"})

        elif action == "get_recent_logs":
            logs = await self.get_recent_audit_logs()
            await self.send_json({"event": "recent_logs", "data": logs})

    async def auditoria_event(self, event):
        """Processar evento de auditoria"""
        await self.send_json(event["data"])

    async def alerta_suspeito(self, event):
        """Processar alerta de atividade suspeita"""
        await self.send_json(
            {
                "event": "alerta_suspeito",
                "data": event["data"],
                "priority": "HIGH",
                "timestamp": await self.get_timestamp(),
            }
        )

    @database_sync_to_async
    def user_is_auditor(self, user):
        """Verificar se usuário é auditor"""
        return user.is_superuser or user.groups.filter(name__in=["Auditores", "Administradores"]).exists()

    @database_sync_to_async
    def get_audit_access_level(self):
        """Obter nível de acesso de auditoria"""
        if self.user.is_superuser:
            return "full"
        elif self.user.groups.filter(name="Administradores").exists():
            return "admin"
        elif self.user.groups.filter(name="Auditores").exists():
            return "audit"
        return "read"

    @database_sync_to_async
    def get_recent_audit_logs(self):
        """Obter logs recentes de auditoria"""
        from estoque.models import LogAuditoriaEstoque

        queryset = LogAuditoriaEstoque.objects.select_related("usuario", "produto", "deposito").order_by("-criado_em")[
            :50
        ]

        if hasattr(self.user, "tenant"):
            queryset = queryset.filter(tenant=self.user.tenant)

        return list(
            queryset.values(
                "id",
                "tipo",
                "produto__nome",
                "deposito__nome",
                "quantidade",
                "usuario__first_name",
                "usuario__last_name",
                "motivo",
                "criado_em",
            )
        )

    @database_sync_to_async
    def get_timestamp(self):
        """Obter timestamp atual"""
        from django.utils import timezone

        return timezone.now().isoformat()

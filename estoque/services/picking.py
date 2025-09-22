"""Sistema de Picking - Separação de Pedidos"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from estoque.models import LogAuditoriaEstoque, PedidoSeparacao, ReservaEstoque

User = get_user_model()


class PickingService:
    """Serviços para sistema de picking/separação"""

    STATUS_TRANSITIONS = {
        "PENDENTE": ["EM_SEPARACAO", "CANCELADO"],
        "EM_SEPARACAO": ["SEPARADO", "PENDENTE", "CANCELADO"],
        "SEPARADO": ["CONFERIDO", "PENDENTE"],
        "CONFERIDO": ["FINALIZADO"],
        "FINALIZADO": [],  # Estado final
        "CANCELADO": [],  # Estado final
    }

    @classmethod
    @transaction.atomic
    def criar_pedido_separacao(
        cls,
        itens_produtos,
        origem_tipo,
        origem_id,
        usuario_solicitante,
        prioridade="NORMAL",
        observacoes=None,
        tenant=None,
    ):
        """Cria pedido de separação com múltiplos produtos

        Args:
            itens_produtos: Lista de dicts [{'produto_id': int, 'deposito_id': int, 'quantidade': Decimal}]
            origem_tipo: str - Tipo da origem ('VENDA', 'TRANSFERENCIA', etc.)
            origem_id: int - ID da origem
            usuario_solicitante: User
            prioridade: str - 'BAIXA', 'NORMAL', 'ALTA', 'URGENTE'
            observacoes: str
            tenant: Tenant

        """
        # Validar itens
        if not itens_produtos:
            raise ValidationError("Pedido de separação deve ter pelo menos um item")

        # Verificar disponibilidade de todos os itens
        reservas_criadas = []

        try:
            # Criar reservas para todos os itens
            for item in itens_produtos:
                from estoque.services.reservas import ReservaService

                reserva = ReservaService.criar_reserva(
                    produto_id=item["produto_id"],
                    deposito_id=item["deposito_id"],
                    quantidade=item["quantidade"],
                    origem_tipo="PICKING",
                    origem_id=None,  # Será atualizado depois
                    usuario=usuario_solicitante,
                    tenant=tenant,
                    motivo=f"Reserva para separação - {origem_tipo}",
                )
                reservas_criadas.append(reserva)

            # Criar pedido de separação
            pedido = PedidoSeparacao.objects.create(
                origem_tipo=origem_tipo,
                origem_id=origem_id,
                prioridade=prioridade,
                observacoes=observacoes,
                criado_por=usuario_solicitante,
                tenant=tenant,
            )

            # Atualizar origem_id das reservas
            for reserva in reservas_criadas:
                reserva.origem_id = str(pedido.id)
                reserva.save(update_fields=["origem_id"])

            # Log de criação
            LogAuditoriaEstoque.objects.create(
                tipo="PEDIDO_SEPARACAO_CRIADO",
                produto=None,  # Múltiplos produtos
                deposito=None,
                quantidade=sum(item["quantidade"] for item in itens_produtos),
                usuario=usuario_solicitante,
                motivo=f"Criação de pedido de separação #{pedido.id}",
                metadata={
                    "pedido_id": pedido.id,
                    "origem_tipo": origem_tipo,
                    "origem_id": origem_id,
                    "total_itens": len(itens_produtos),
                    "prioridade": prioridade,
                },
                tenant=tenant,
            )

            # Broadcast WebSocket
            cls._broadcast_picking_event(
                {
                    "event": "picking.pedido_criado",
                    "pedido_id": pedido.id,
                    "prioridade": prioridade,
                    "total_itens": len(reservas_criadas),
                },
                tenant,
            )

            return pedido

        except Exception as e:
            # Reverter reservas criadas em caso de erro
            for reserva in reservas_criadas:
                try:
                    from estoque.services.reservas import ReservaService

                    ReservaService.cancelar_reserva(reserva.id, usuario_solicitante, "Erro na criação do pedido")
                except Exception:
                    pass
            raise e

    @classmethod
    @transaction.atomic
    def iniciar_separacao(cls, pedido_id, usuario_separador):
        """Inicia processo de separação"""
        pedido = PedidoSeparacao.objects.select_for_update().get(id=pedido_id)

        if not cls._pode_transicionar(pedido.status, "EM_SEPARACAO"):
            raise ValidationError(f"Não é possível iniciar separação. Status atual: {pedido.status}")

        # Verificar se outro usuário não está separando
        if pedido.status == "EM_SEPARACAO" and pedido.separador and pedido.separador != usuario_separador:
            raise ValidationError(f"Pedido sendo separado por {pedido.separador.get_full_name()}")

        # Atualizar pedido
        pedido.status = "EM_SEPARACAO"
        pedido.separador = usuario_separador
        pedido.iniciado_em = timezone.now()
        pedido.save()

        # Log
        LogAuditoriaEstoque.objects.create(
            tipo="SEPARACAO_INICIADA",
            produto=None,
            deposito=None,
            quantidade=None,
            usuario=usuario_separador,
            motivo=f"Início de separação do pedido #{pedido.id}",
            metadata={
                "pedido_id": pedido.id,
                "separador_id": usuario_separador.id,
                "separador_nome": usuario_separador.get_full_name(),
            },
            tenant=pedido.tenant,
        )

        # Broadcast
        cls._broadcast_picking_event(
            {
                "event": "picking.separacao_iniciada",
                "pedido_id": pedido.id,
                "separador_nome": usuario_separador.get_full_name(),
            },
            pedido.tenant,
        )

        return pedido

    @classmethod
    @transaction.atomic
    def finalizar_separacao(cls, pedido_id, usuario_separador, observacoes_separacao=None):
        """Finaliza separação (marca como SEPARADO)"""
        pedido = PedidoSeparacao.objects.select_for_update().get(id=pedido_id)

        if pedido.status != "EM_SEPARACAO":
            raise ValidationError("Pedido não está em separação")

        if pedido.separador != usuario_separador:
            raise ValidationError("Apenas o separador pode finalizar")

        # Atualizar pedido
        pedido.status = "SEPARADO"
        pedido.separado_em = timezone.now()
        pedido.observacoes_separacao = observacoes_separacao
        pedido.save()

        # Log
        LogAuditoriaEstoque.objects.create(
            tipo="SEPARACAO_FINALIZADA",
            produto=None,
            deposito=None,
            quantidade=None,
            usuario=usuario_separador,
            motivo=f"Separação finalizada do pedido #{pedido.id}",
            metadata={"pedido_id": pedido.id, "tempo_separacao_minutos": cls._calcular_tempo_separacao(pedido)},
            tenant=pedido.tenant,
        )

        # Broadcast
        cls._broadcast_picking_event({"event": "picking.separacao_finalizada", "pedido_id": pedido.id}, pedido.tenant)

        return pedido

    @classmethod
    @transaction.atomic
    def conferir_separacao(cls, pedido_id, usuario_conferente, itens_conferidos=None, observacoes_conferencia=None):
        """Confere separação

        Args:
            itens_conferidos: Lista de dicts com ajustes se necessário
                             [{'reserva_id': int, 'quantidade_conferida': Decimal}]

        """
        pedido = PedidoSeparacao.objects.select_for_update().get(id=pedido_id)

        if pedido.status != "SEPARADO":
            raise ValidationError("Pedido não está separado para conferência")

        # Processar ajustes se houver
        ajustes_realizados = []
        if itens_conferidos:
            reservas = ReservaEstoque.objects.filter(origem_tipo="PICKING", origem_id=str(pedido.id), status="ATIVA")

            for item in itens_conferidos:
                reserva = reservas.filter(id=item["reserva_id"]).first()
                if reserva and item["quantidade_conferida"] != reserva.quantidade:
                    # Ajustar reserva
                    diferenca = item["quantidade_conferida"] - reserva.quantidade
                    if diferenca != 0:
                        from estoque.services.reservas import ReservaService

                        if diferenca > 0:
                            # Aumentar reserva
                            ReservaService.criar_reserva(
                                produto_id=reserva.produto.id,
                                deposito_id=reserva.deposito.id,
                                quantidade=diferenca,
                                origem_tipo="PICKING",
                                origem_id=str(pedido.id),
                                usuario=usuario_conferente,
                                tenant=pedido.tenant,
                                motivo="Ajuste na conferência",
                            )
                        else:
                            # Reduzir reserva (consumo parcial)
                            ReservaService.consumir_reserva(
                                reserva_id=reserva.id,
                                quantidade=abs(diferenca),
                                usuario=usuario_conferente,
                                motivo="Ajuste na conferência",
                            )

                        ajustes_realizados.append(
                            {
                                "reserva_id": reserva.id,
                                "produto_nome": reserva.produto.nome,
                                "quantidade_original": float(reserva.quantidade),
                                "quantidade_conferida": float(item["quantidade_conferida"]),
                                "diferenca": float(diferenca),
                            },
                        )

        # Atualizar pedido
        pedido.status = "CONFERIDO"
        pedido.conferente = usuario_conferente
        pedido.conferido_em = timezone.now()
        pedido.observacoes_conferencia = observacoes_conferencia
        pedido.save()

        # Log
        LogAuditoriaEstoque.objects.create(
            tipo="SEPARACAO_CONFERIDA",
            produto=None,
            deposito=None,
            quantidade=None,
            usuario=usuario_conferente,
            motivo=f"Conferência do pedido #{pedido.id}",
            metadata={
                "pedido_id": pedido.id,
                "conferente_id": usuario_conferente.id,
                "conferente_nome": usuario_conferente.get_full_name(),
                "ajustes_realizados": ajustes_realizados,
                "total_ajustes": len(ajustes_realizados),
            },
            tenant=pedido.tenant,
        )

        # Broadcast
        cls._broadcast_picking_event(
            {
                "event": "picking.separacao_conferida",
                "pedido_id": pedido.id,
                "ajustes_realizados": len(ajustes_realizados),
            },
            pedido.tenant,
        )

        return pedido

    @classmethod
    @transaction.atomic
    def finalizar_pedido(cls, pedido_id, usuario_finalizador):
        """Finaliza pedido consumindo todas as reservas"""
        pedido = PedidoSeparacao.objects.select_for_update().get(id=pedido_id)

        if pedido.status != "CONFERIDO":
            raise ValidationError("Pedido não está conferido para finalização")

        # Consumir todas as reservas ativas do pedido
        reservas = ReservaEstoque.objects.filter(origem_tipo="PICKING", origem_id=str(pedido.id), status="ATIVA")

        movimentos_gerados = []
        from estoque.services.reservas import ReservaService

        for reserva in reservas:
            movimento = ReservaService.consumir_reserva(
                reserva_id=reserva.id,
                usuario=usuario_finalizador,
                motivo=f"Finalização do pedido de separação #{pedido.id}",
            )
            movimentos_gerados.append(movimento)

        # Atualizar pedido
        pedido.status = "FINALIZADO"
        pedido.finalizado_em = timezone.now()
        pedido.finalizador = usuario_finalizador
        pedido.save()

        # Log
        LogAuditoriaEstoque.objects.create(
            tipo="PEDIDO_SEPARACAO_FINALIZADO",
            produto=None,
            deposito=None,
            quantidade=None,
            usuario=usuario_finalizador,
            motivo=f"Finalização do pedido #{pedido.id}",
            metadata={
                "pedido_id": pedido.id,
                "movimentos_gerados": len(movimentos_gerados),
                "tempo_total_minutos": cls._calcular_tempo_total(pedido),
            },
            tenant=pedido.tenant,
        )

        # Broadcast
        cls._broadcast_picking_event(
            {
                "event": "picking.pedido_finalizado",
                "pedido_id": pedido.id,
                "movimentos_gerados": len(movimentos_gerados),
            },
            pedido.tenant,
        )

        return pedido

    @classmethod
    @transaction.atomic
    def cancelar_pedido(cls, pedido_id, usuario, motivo_cancelamento):
        """Cancela pedido liberando reservas"""
        pedido = PedidoSeparacao.objects.select_for_update().get(id=pedido_id)

        if pedido.status in ["FINALIZADO", "CANCELADO"]:
            raise ValidationError("Pedido não pode ser cancelado")

        # Cancelar todas as reservas
        reservas = ReservaEstoque.objects.filter(origem_tipo="PICKING", origem_id=str(pedido.id), status="ATIVA")

        from estoque.services.reservas import ReservaService

        for reserva in reservas:
            ReservaService.cancelar_reserva(
                reserva_id=reserva.id,
                usuario=usuario,
                motivo=f"Cancelamento do pedido #{pedido.id}: {motivo_cancelamento}",
            )

        # Atualizar pedido
        pedido.status = "CANCELADO"
        pedido.cancelado_em = timezone.now()
        pedido.motivo_cancelamento = motivo_cancelamento
        pedido.save()

        # Log
        LogAuditoriaEstoque.objects.create(
            tipo="PEDIDO_SEPARACAO_CANCELADO",
            produto=None,
            deposito=None,
            quantidade=None,
            usuario=usuario,
            motivo=f"Cancelamento do pedido #{pedido.id}: {motivo_cancelamento}",
            metadata={"pedido_id": pedido.id, "reservas_canceladas": len(reservas)},
            tenant=pedido.tenant,
        )

        # Broadcast
        cls._broadcast_picking_event({"event": "picking.pedido_cancelado", "pedido_id": pedido.id}, pedido.tenant)

        return pedido

    @classmethod
    def listar_pedidos_por_status(cls, status=None, usuario=None, tenant=None):
        """Lista pedidos por status"""
        queryset = PedidoSeparacao.objects.select_related("criado_por", "separador", "conferente").order_by(
            "-criado_em",
        )

        if status:
            queryset = queryset.filter(status=status)
        if usuario:
            queryset = queryset.filter(separador=usuario)
        if tenant:
            queryset = queryset.filter(tenant=tenant)

        return queryset

    @classmethod
    def estatisticas_picking(cls, tenant=None, dias=30):
        """Estatísticas do sistema de picking"""
        from datetime import timedelta

        data_limite = timezone.now() - timedelta(days=dias)

        queryset = PedidoSeparacao.objects.filter(criado_em__gte=data_limite)

        if tenant:
            queryset = queryset.filter(tenant=tenant)

        return {
            "total_pedidos": queryset.count(),
            "pendentes": queryset.filter(status="PENDENTE").count(),
            "em_separacao": queryset.filter(status="EM_SEPARACAO").count(),
            "separados": queryset.filter(status="SEPARADO").count(),
            "conferidos": queryset.filter(status="CONFERIDO").count(),
            "finalizados": queryset.filter(status="FINALIZADO").count(),
            "cancelados": queryset.filter(status="CANCELADO").count(),
            "tempo_medio_separacao": cls._calcular_tempo_medio_separacao(queryset),
            "produtividade_separadores": cls._calcular_produtividade_separadores(queryset),
        }

    # Métodos auxiliares

    @classmethod
    def _pode_transicionar(cls, status_atual, novo_status):
        """Verifica se transição de status é válida"""
        return novo_status in cls.STATUS_TRANSITIONS.get(status_atual, [])

    @classmethod
    def _calcular_tempo_separacao(cls, pedido):
        """Calcula tempo de separação em minutos"""
        if pedido.iniciado_em and pedido.separado_em:
            delta = pedido.separado_em - pedido.iniciado_em
            return int(delta.total_seconds() / 60)
        return 0

    @classmethod
    def _calcular_tempo_total(cls, pedido):
        """Calcula tempo total em minutos"""
        if pedido.criado_em and pedido.finalizado_em:
            delta = pedido.finalizado_em - pedido.criado_em
            return int(delta.total_seconds() / 60)
        return 0

    @classmethod
    def _calcular_tempo_medio_separacao(cls, queryset):
        """Calcula tempo médio de separação"""
        separados = queryset.filter(
            status__in=["SEPARADO", "CONFERIDO", "FINALIZADO"],
            iniciado_em__isnull=False,
            separado_em__isnull=False,
        )

        tempos = []
        for pedido in separados:
            tempo = cls._calcular_tempo_separacao(pedido)
            if tempo > 0:
                tempos.append(tempo)

        return sum(tempos) / len(tempos) if tempos else 0

    @classmethod
    def _calcular_produtividade_separadores(cls, queryset):
        """Calcula produtividade por separador"""
        from django.db.models import Count

        return (
            queryset.filter(status="FINALIZADO", separador__isnull=False)
            .values("separador__id", "separador__first_name", "separador__last_name")
            .annotate(total_pedidos=Count("id"))
            .order_by("-total_pedidos")
        )

    @classmethod
    def _broadcast_picking_event(cls, payload, tenant=None):
        """Broadcast de eventos de picking via WebSocket"""
        try:
            layer = get_channel_layer()
            grupos = ["picking_stream"]
            if tenant:
                grupos.append(f"picking_tenant_{tenant.id}")

            for grupo in grupos:
                async_to_sync(layer.group_send)(grupo, {"type": "picking_event", "data": payload})
        except Exception:
            pass

"""
API ViewSets para Reservas de Estoque - CRUD Completo
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from estoque.api.serializers import (
    ReservaEstoqueCreateSerializer,
    ReservaEstoqueSerializer,
    ReservaEstoqueUpdateSerializer,
)
from estoque.models import EstoqueSaldo, ReservaEstoque
from estoque.services.reservas import ReservaService


class ReservaEstoqueViewSet(viewsets.ModelViewSet):
    """ViewSet completo para gestão de reservas de estoque"""

    queryset = ReservaEstoque.objects.select_related("produto", "deposito").order_by("-criado_em")

    serializer_class = ReservaEstoqueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    filterset_fields = {
        "produto": ["exact"],
        "deposito": ["exact"],
        "status": ["exact"],
        "origem_tipo": ["exact"],
        "origem_id": ["exact"],
        "criado_em": ["gte", "lte"],
        "expira_em": ["gte", "lte"],
    }

    search_fields = ["produto__nome", "produto__sku"]
    ordering_fields = ["criado_em", "expira_em", "quantidade"]

    def get_serializer_class(self):
        """Usa serializers específicos para cada ação"""
        if self.action == "create":
            return ReservaEstoqueCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ReservaEstoqueUpdateSerializer
        return ReservaEstoqueSerializer

    def get_permissions(self):
        """Permissões básicas por ação"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Criar nova reserva com validações de negócio"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Usar service layer para criar reserva
            reserva = ReservaService.criar_reserva(
                produto_id=serializer.validated_data["produto"].id,
                deposito_id=serializer.validated_data["deposito"].id,
                quantidade=serializer.validated_data["quantidade"],
                origem_tipo=serializer.validated_data["origem_tipo"],
                origem_id=serializer.validated_data.get("origem_id"),
                expira_em=serializer.validated_data.get("expira_em"),
                usuario=request.user,
                tenant=getattr(request, "tenant", None),
            )

            response_serializer = ReservaEstoqueSerializer(reserva)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Atualizar reserva existente"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Verificar se reserva pode ser alterada
        if instance.status != "ATIVA":
            return Response(
                {"detail": "Apenas reservas ativas podem ser alteradas"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Se quantidade mudou, revalidar disponibilidade
                if "quantidade" in serializer.validated_data:
                    nova_quantidade = serializer.validated_data["quantidade"]
                    diferenca = nova_quantidade - instance.quantidade

                    if diferenca > 0:
                        # Aumentou - verificar se tem saldo
                        saldo = EstoqueSaldo.objects.select_for_update().get(
                            produto=instance.produto, deposito=instance.deposito
                        )

                        if saldo.disponivel < diferenca:
                            return Response(
                                {"detail": f"Saldo insuficiente. Disponível: {saldo.disponivel}"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Atualizar saldo
                        saldo.reservado += diferenca
                        saldo.save()

                    elif diferenca < 0:
                        # Diminuiu - liberar saldo
                        saldo = EstoqueSaldo.objects.select_for_update().get(
                            produto=instance.produto, deposito=instance.deposito
                        )
                        saldo.reservado += diferenca  # diferenca é negativa
                        saldo.save()

                # Salvar reserva
                self.perform_update(serializer)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Cancelar/excluir reserva"""
        instance = self.get_object()

        try:
            ReservaService.cancelar_reserva(instance.id, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def consumir(self, request, pk=None):
        """Consumir reserva (gerar movimento de saída)"""
        reserva = self.get_object()

        if reserva.status != "ATIVA":
            return Response(
                {"detail": "Apenas reservas ativas podem ser consumidas"}, status=status.HTTP_400_BAD_REQUEST
            )

        quantidade = request.data.get("quantidade", reserva.quantidade)
        motivo = request.data.get("motivo", "Consumo de reserva")

        try:
            movimento = ReservaService.consumir_reserva(
                reserva_id=reserva.id, quantidade=quantidade, usuario=request.user, motivo=motivo
            )

            return Response(
                {
                    "detail": "Reserva consumida com sucesso",
                    "movimento_id": movimento.id,
                    "quantidade_consumida": float(quantidade),
                }
            )

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Cancelar reserva específica"""
        reserva = self.get_object()
        motivo = request.data.get("motivo", "Cancelamento manual")

        try:
            ReservaService.cancelar_reserva(reserva.id, request.user, motivo)
            return Response({"detail": "Reserva cancelada com sucesso"})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def expirar_vencidas(self, request):
        """Expirar reservas vencidas (endpoint administrativo)"""
        if not request.user.is_staff:
            return Response({"detail": "Permissão insuficiente"}, status=status.HTTP_403_FORBIDDEN)

        agora = timezone.now()
        tenant = getattr(request, "tenant", None)
        reservas_vencidas = ReservaEstoque.objects.filter(
            status="ATIVA",
            expira_em__lt=agora,
        )
        if tenant:
            reservas_vencidas = reservas_vencidas.filter(tenant=tenant)

        total_expiradas = 0
        for reserva in reservas_vencidas:
            try:
                ReservaService.expirar_reserva(reserva.id)
                total_expiradas += 1
            except Exception:
                # Log erro mas continua processando
                continue

        return Response({"detail": f"{total_expiradas} reservas expiradas com sucesso"})

    @action(detail=False)
    def resumo(self, request):
        """Resumo das reservas por status"""
        from django.db.models import Count, Q, Sum

        queryset = self.filter_queryset(self.get_queryset())

        resumo = queryset.aggregate(
            total=Count("id"),
            ativas=Count("id", filter=Q(status="ATIVA")),
            consumidas=Count("id", filter=Q(status="CONSUMIDA")),
            canceladas=Count("id", filter=Q(status="CANCELADA")),
            expiradas=Count("id", filter=Q(status="EXPIRADA")),
            quantidade_total=Sum("quantidade"),
            quantidade_ativa=Sum("quantidade", filter=Q(status="ATIVA")),
        )

        return Response(resumo)

    @action(detail=False)
    def alertas_expiracao(self, request):
        """Reservas próximas do vencimento"""
        horas = int(request.query_params.get("horas", 24))
        limite = timezone.now() + timedelta(hours=horas)

        reservas_expirando = (
            self.get_queryset()
            .filter(status="ATIVA", expira_em__lte=limite, expira_em__gt=timezone.now())
            .select_related("produto", "deposito")
            .order_by("expira_em")
        )

        serializer = self.get_serializer(reservas_expirando, many=True)
        return Response({"total": len(serializer.data), "horas_limite": horas, "reservas": serializer.data})

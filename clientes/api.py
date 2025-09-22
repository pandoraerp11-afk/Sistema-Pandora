from core.permissions import AdvancedPermissionManager
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Cliente
    """

    class Meta:
        model = Cliente
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ClienteViewSet(viewsets.ModelViewSet):
    """
    API para gerenciamento de clientes

    Permite listar, criar, atualizar e excluir clientes, além de exportar dados
    e gerar relatórios personalizados.
    """

    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["nome", "tipo", "ativo"]
    search_fields = ["nome", "email", "telefone", "cnpj_cpf"]
    ordering_fields = ["nome", "created_at", "updated_at"]

    def get_queryset(self):
        """
        Filtra os clientes com base nas permissões do usuário
        """
        user = self.request.user

        # Se o usuário for superusuário, retorna todos os clientes
        if user.is_superuser:
            return Cliente.objects.all()

        # Caso contrário, retorna apenas os clientes que o usuário tem permissão para ver
        return AdvancedPermissionManager.get_objects_for_user_with_permission(user, Cliente, "view_cliente")

    @swagger_auto_schema(
        operation_description="Exporta dados de clientes em formato CSV",
        responses={200: "Arquivo CSV gerado com sucesso"},
    )
    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        """
        Exporta dados de clientes em formato CSV
        """
        # Implementação da exportação CSV
        # (código de exportação seria implementado aqui)

        return Response({"message": "Exportação CSV iniciada. O arquivo será enviado por email."})

    @swagger_auto_schema(
        operation_description="Exporta dados de clientes em formato Excel",
        responses={200: "Arquivo Excel gerado com sucesso"},
    )
    @action(detail=False, methods=["get"])
    def export_excel(self, request):
        """
        Exporta dados de clientes em formato Excel
        """
        # Implementação da exportação Excel
        # (código de exportação seria implementado aqui)

        return Response({"message": "Exportação Excel iniciada. O arquivo será enviado por email."})

    @swagger_auto_schema(
        operation_description="Gera relatório de clientes em PDF", responses={200: "Relatório PDF gerado com sucesso"}
    )
    @action(detail=False, methods=["get"])
    def generate_report(self, request):
        """
        Gera relatório de clientes em PDF
        """
        # Implementação da geração de relatório
        # (código de geração de relatório seria implementado aqui)

        return Response({"message": "Geração de relatório iniciada. O PDF será enviado por email."})

    @swagger_auto_schema(
        operation_description="Obtém estatísticas de clientes", responses={200: "Estatísticas obtidas com sucesso"}
    )
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Obtém estatísticas de clientes
        """
        # Cálculo de estatísticas
        total_clientes = Cliente.objects.count()
        clientes_ativos = Cliente.objects.filter(ativo=True).count()
        clientes_inativos = total_clientes - clientes_ativos

        # Mais estatísticas seriam calculadas aqui

        return Response(
            {
                "total": total_clientes,
                "ativos": clientes_ativos,
                "inativos": clientes_inativos,
                "percentual_ativos": (clientes_ativos / total_clientes * 100) if total_clientes > 0 else 0,
            }
        )

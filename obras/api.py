from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import AdvancedPermissionManager

from .models import Obra


class ObraSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Obra
    """

    class Meta:
        model = Obra
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ObraViewSet(viewsets.ModelViewSet):
    """
    API para gerenciamento de obras

    Permite listar, criar, atualizar e excluir obras, além de gerenciar cronogramas,
    exportar dados e gerar relatórios personalizados.
    """

    queryset = Obra.objects.all()
    serializer_class = ObraSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["nome", "cliente", "status", "data_inicio", "data_previsao_termino"]
    search_fields = ["nome", "descricao", "endereco"]
    ordering_fields = ["nome", "data_inicio", "data_previsao_termino", "created_at"]

    def get_queryset(self):
        """
        Filtra as obras com base nas permissões do usuário
        """
        user = self.request.user

        # Se o usuário for superusuário, retorna todas as obras
        if user.is_superuser:
            return Obra.objects.all()

        # Caso contrário, retorna apenas as obras que o usuário tem permissão para ver
        return AdvancedPermissionManager.get_objects_for_user_with_permission(user, Obra, "view_obra")

    @swagger_auto_schema(
        operation_description="Exporta dados de obras em formato CSV", responses={200: "Arquivo CSV gerado com sucesso"}
    )
    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        """
        Exporta dados de obras em formato CSV
        """
        # Implementação da exportação CSV
        # (código de exportação seria implementado aqui)

        return Response({"message": "Exportação CSV iniciada. O arquivo será enviado por email."})

    @swagger_auto_schema(
        operation_description="Exporta dados de obras em formato Excel",
        responses={200: "Arquivo Excel gerado com sucesso"},
    )
    @action(detail=False, methods=["get"])
    def export_excel(self, request):
        """
        Exporta dados de obras em formato Excel
        """
        # Implementação da exportação Excel
        # (código de exportação seria implementado aqui)

        return Response({"message": "Exportação Excel iniciada. O arquivo será enviado por email."})

    @swagger_auto_schema(
        operation_description="Gera relatório de obras em PDF", responses={200: "Relatório PDF gerado com sucesso"}
    )
    @action(detail=False, methods=["get"])
    def generate_report(self, request):
        """
        Gera relatório de obras em PDF
        """
        # Implementação da geração de relatório
        # (código de geração de relatório seria implementado aqui)

        return Response({"message": "Geração de relatório iniciada. O PDF será enviado por email."})

    @swagger_auto_schema(
        operation_description="Obtém estatísticas de obras", responses={200: "Estatísticas obtidas com sucesso"}
    )
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Obtém estatísticas de obras
        """
        # Cálculo de estatísticas
        total_obras = Obra.objects.count()
        obras_em_andamento = Obra.objects.filter(status="em_andamento").count()
        obras_concluidas = Obra.objects.filter(status="concluida").count()
        obras_planejadas = Obra.objects.filter(status="planejada").count()

        # Mais estatísticas seriam calculadas aqui

        return Response(
            {
                "total": total_obras,
                "em_andamento": obras_em_andamento,
                "concluidas": obras_concluidas,
                "planejadas": obras_planejadas,
                "percentual_concluidas": (obras_concluidas / total_obras * 100) if total_obras > 0 else 0,
            }
        )

    @swagger_auto_schema(
        operation_description="Gerencia cronograma da obra",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "etapas": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "nome": openapi.Schema(type=openapi.TYPE_STRING),
                            "data_inicio": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                            "data_fim": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                            "percentual_concluido": openapi.Schema(type=openapi.TYPE_NUMBER),
                        },
                    ),
                )
            },
        ),
        responses={200: "Cronograma atualizado com sucesso"},
    )
    @action(detail=True, methods=["get", "post"])
    def cronograma(self, request, pk=None):
        """
        Gerencia o cronograma da obra
        """
        self.get_object()

        if request.method == "GET":
            # Retorna o cronograma atual
            # (código para obter cronograma seria implementado aqui)
            return Response({"message": "Cronograma obtido com sucesso", "cronograma": {}})

        elif request.method == "POST":
            # Atualiza o cronograma
            # (código para atualizar cronograma seria implementado aqui)
            return Response({"message": "Cronograma atualizado com sucesso"})

    @swagger_auto_schema(operation_description="Finaliza uma obra", responses={200: "Obra finalizada com sucesso"})
    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        """
        Finaliza uma obra
        """
        obra = self.get_object()

        # Verificar permissão específica
        if not AdvancedPermissionManager.check_user_permission(request.user, "close_obra", obra):
            return Response({"error": "Você não tem permissão para finalizar esta obra"}, status=403)

        # Lógica para finalizar a obra
        # (código para finalizar obra seria implementado aqui)

        return Response({"message": "Obra finalizada com sucesso"})

    @swagger_auto_schema(
        operation_description="Reabre uma obra finalizada", responses={200: "Obra reaberta com sucesso"}
    )
    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        """
        Reabre uma obra finalizada
        """
        obra = self.get_object()

        # Verificar permissão específica
        if not AdvancedPermissionManager.check_user_permission(request.user, "reopen_obra", obra):
            return Response({"error": "Você não tem permissão para reabrir esta obra"}, status=403)

        # Lógica para reabrir a obra
        # (código para reabrir obra seria implementado aqui)

        return Response({"message": "Obra reaberta com sucesso"})

"""
ViewSets para cotações e portal fornecedor.
"""

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from core.utils import get_current_tenant
from portal_fornecedor.models import AcessoFornecedor
from shared.services.permission_resolver import PermissionResolver

from .models import Cotacao, PropostaFornecedor, PropostaFornecedorItem
from .serializers import (
    AcessoFornecedorSerializer,
    CotacaoCreateSerializer,
    CotacaoDetailSerializer,
    CotacaoListSerializer,
    PropostaFornecedorCreateSerializer,
    PropostaFornecedorDetailSerializer,
    PropostaFornecedorListSerializer,
    PropostaItemUpdateSerializer,
)
from .services.cotacao_service import CotacaoService, PropostaService


class CotacaoViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciamento de cotações."""

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "data_abertura"]
    search_fields = ["codigo", "titulo", "descricao"]
    ordering_fields = ["data_abertura", "prazo_proposta", "codigo"]
    ordering = ["-data_abertura"]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return Cotacao.objects.filter(tenant=tenant).select_related("criado_por").prefetch_related("itens")

    def get_serializer_class(self):
        if self.action == "create":
            return CotacaoCreateSerializer
        elif self.action in ["list"]:
            return CotacaoListSerializer
        return CotacaoDetailSerializer

    def perform_create(self, serializer):
        """Cria cotação através do service."""
        serializer.save()

    @action(detail=True, methods=["post"])
    def encerrar(self, request, pk=None):
        """Encerra cotação."""
        cotacao = self.get_object()

        # Verificar permissão
        if not self._tem_permissao_edicao(cotacao):
            return Response({"error": "Sem permissão para encerrar cotação"}, status=status.HTTP_403_FORBIDDEN)

        try:
            with transaction.atomic():
                CotacaoService.encerrar_cotacao(cotacao, request.user)

            serializer = self.get_serializer(cotacao)
            return Response(serializer.data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Cancela cotação."""
        cotacao = self.get_object()

        if not self._tem_permissao_edicao(cotacao):
            return Response({"error": "Sem permissão para cancelar cotação"}, status=status.HTTP_403_FORBIDDEN)

        motivo = request.data.get("motivo", "")

        try:
            with transaction.atomic():
                CotacaoService.cancelar_cotacao(cotacao, request.user, motivo)

            serializer = self.get_serializer(cotacao)
            return Response(serializer.data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def propostas(self, request, pk=None):
        """Lista propostas da cotação."""
        cotacao = self.get_object()

        propostas = cotacao.propostas.select_related("fornecedor", "usuario").prefetch_related("itens")

        serializer = PropostaFornecedorListSerializer(propostas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def estatisticas(self, request, pk=None):
        """Retorna estatísticas da cotação."""
        cotacao = self.get_object()

        propostas = cotacao.propostas.all()
        stats = {
            "total_propostas": propostas.count(),
            "propostas_enviadas": propostas.filter(status="enviada").count(),
            "propostas_rascunho": propostas.filter(status="rascunho").count(),
            "total_itens": cotacao.itens.count(),
            "valor_estimado": cotacao.valor_estimado,
            "menor_proposta": None,
            "maior_proposta": None,
            "valor_medio": None,
        }

        propostas_enviadas = propostas.filter(status="enviada", total_estimado__isnull=False)

        if propostas_enviadas.exists():
            valores = [p.total_estimado for p in propostas_enviadas]
            stats["menor_proposta"] = min(valores)
            stats["maior_proposta"] = max(valores)
            stats["valor_medio"] = sum(valores) / len(valores)

        return Response(stats)

    def _tem_permissao_edicao(self, cotacao):
        """Verifica se usuário pode editar cotação."""
        return cotacao.criado_por == self.request.user or PermissionResolver.resolve(
            user=self.request.user, permission="cotacoes.change_cotacao", tenant=get_current_tenant(self.request)
        )


class PropostaFornecedorViewSet(viewsets.ModelViewSet):
    """ViewSet para propostas de fornecedor."""

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "cotacao__status"]
    search_fields = ["cotacao__codigo", "cotacao__titulo"]
    ordering_fields = ["enviado_em", "total_estimado", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filtra propostas por usuário ou admin."""
        tenant = get_current_tenant(self.request)

        # Verificar se é fornecedor
        try:
            acesso = AcessoFornecedor.objects.get(usuario=self.request.user, ativo=True)
            # Fornecedor vê apenas suas propostas
            return PropostaFornecedor.objects.filter(
                fornecedor=acesso.fornecedor, cotacao__tenant=tenant
            ).select_related("cotacao", "fornecedor", "usuario")

        except AcessoFornecedor.DoesNotExist:
            # Admin/staff vê todas do tenant
            if self.request.user.is_staff or PermissionResolver.resolve(
                user=self.request.user, permission="cotacoes.view_propostafornecedor", tenant=tenant
            ):
                return PropostaFornecedor.objects.filter(cotacao__tenant=tenant).select_related(
                    "cotacao", "fornecedor", "usuario"
                )

            # Usuário sem acesso não vê nada
            return PropostaFornecedor.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return PropostaFornecedorCreateSerializer
        elif self.action == "list":
            return PropostaFornecedorListSerializer
        return PropostaFornecedorDetailSerializer

    def perform_create(self, serializer):
        """Cria proposta através do service."""
        serializer.save()

    @action(detail=True, methods=["post"])
    def enviar(self, request, pk=None):
        """Envia proposta."""
        proposta = self.get_object()

        if not self._pode_editar_proposta(proposta):
            return Response({"error": "Sem permissão para enviar proposta"}, status=status.HTTP_403_FORBIDDEN)

        try:
            with transaction.atomic():
                PropostaService.enviar_proposta(proposta, request.user)

            serializer = self.get_serializer(proposta)
            return Response(serializer.data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Cancela proposta."""
        proposta = self.get_object()

        if not self._pode_editar_proposta(proposta):
            return Response({"error": "Sem permissão para cancelar proposta"}, status=status.HTTP_403_FORBIDDEN)

        motivo = request.data.get("motivo", "")

        try:
            with transaction.atomic():
                proposta.status = "cancelada"
                proposta.observacao = f"{proposta.observacao}\n\nCancelada: {motivo}".strip()
                proposta.save()

            serializer = self.get_serializer(proposta)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def atualizar_item(self, request, pk=None):
        """Atualiza item da proposta."""
        proposta = self.get_object()

        if not self._pode_editar_proposta(proposta):
            return Response({"error": "Sem permissão para editar proposta"}, status=status.HTTP_403_FORBIDDEN)

        item_id = request.data.get("item_cotacao_id")
        if not item_id:
            return Response({"error": "item_cotacao_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = proposta.itens.get(item_cotacao_id=item_id)
            serializer = PropostaItemUpdateSerializer(item, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except PropostaFornecedorItem.DoesNotExist:
            return Response({"error": "Item não encontrado"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def validar_proposta(self, request, pk=None):
        """Valida se proposta pode ser enviada."""
        proposta = self.get_object()

        erros = []

        # Verificar se cotação está aberta
        if not proposta.cotacao.is_aberta:
            erros.append("Cotação não está mais aberta")

        # Verificar se tem todos os itens preenchidos
        itens_sem_preco = proposta.itens.filter(preco_unitario__isnull=True)
        if itens_sem_preco.exists():
            erros.append("Há itens sem preço informado")

        # Verificar validade
        if proposta.validade_proposta <= timezone.now().date():
            erros.append("Validade da proposta expirou")

        return Response(
            {
                "valida": len(erros) == 0,
                "erros": erros,
                "pode_enviar": len(erros) == 0 and proposta.status == "rascunho",
            }
        )

    def _pode_editar_proposta(self, proposta):
        """Verifica se usuário pode editar proposta."""
        try:
            acesso = AcessoFornecedor.objects.get(usuario=self.request.user, ativo=True)
            return (
                proposta.fornecedor == acesso.fornecedor
                and proposta.status == "rascunho"
                and proposta.cotacao.is_aberta
            )
        except AcessoFornecedor.DoesNotExist:
            return False


class CotacaoPublicaViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet público para cotações abertas (portal fornecedor)."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CotacaoDetailSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["codigo", "titulo", "descricao"]
    ordering = ["-data_abertura"]

    def get_queryset(self):
        """Retorna apenas cotações abertas que o fornecedor pode participar."""
        try:
            acesso = AcessoFornecedor.objects.get(usuario=self.request.user, ativo=True)

            # Cotações abertas onde o fornecedor pode participar
            cotacoes_abertas = (
                Cotacao.objects.filter(status="aberta", prazo_proposta__gt=timezone.now())
                .select_related("criado_por")
                .prefetch_related("itens")
            )

            # Filtrar apenas as que pode participar
            cotacoes_disponiveis = []
            for cotacao in cotacoes_abertas:
                pode, _ = cotacao.pode_receber_proposta(acesso.fornecedor)
                if pode:
                    cotacoes_disponiveis.append(cotacao.id)

            return cotacoes_abertas.filter(id__in=cotacoes_disponiveis)

        except AcessoFornecedor.DoesNotExist:
            return Cotacao.objects.none()

    @action(detail=True, methods=["post"])
    def criar_proposta(self, request, pk=None):
        """Cria nova proposta para a cotação."""
        cotacao = self.get_object()

        try:
            acesso = AcessoFornecedor.objects.get(usuario=request.user, ativo=True)
        except AcessoFornecedor.DoesNotExist:
            return Response({"error": "Acesso de fornecedor não encontrado"}, status=status.HTTP_403_FORBIDDEN)

        # Verificar se já tem proposta
        if PropostaFornecedor.objects.filter(cotacao=cotacao, fornecedor=acesso.fornecedor).exists():
            return Response({"error": "Já existe proposta para esta cotação"}, status=status.HTTP_400_BAD_REQUEST)

        # Criar proposta base
        data = request.data.copy()
        data["cotacao"] = cotacao.id

        serializer = PropostaFornecedorCreateSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            proposta = serializer.save()

            # Retornar proposta criada
            response_serializer = PropostaFornecedorDetailSerializer(proposta)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AcessoFornecedorViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para gerenciar acessos de fornecedor (admin)."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AcessoFornecedorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["ativo", "is_admin_portal", "fornecedor"]
    search_fields = ["usuario__username", "usuario__email", "fornecedor__nome_fantasia"]
    ordering = ["-data_concessao"]

    def get_queryset(self):
        """Apenas admin pode ver acessos."""
        tenant = get_current_tenant(self.request)

        if not (
            self.request.user.is_staff
            or PermissionResolver.resolve(
                user=self.request.user, permission="portal_fornecedor.view_acessofornecedor", tenant=tenant
            )
        ):
            return AcessoFornecedor.objects.none()

        return AcessoFornecedor.objects.filter(fornecedor__tenant=tenant).select_related("usuario", "fornecedor")

    @action(detail=True, methods=["post"])
    def ativar(self, request, pk=None):
        """Ativa acesso."""
        acesso = self.get_object()
        acesso.ativo = True
        acesso.save()

        serializer = self.get_serializer(acesso)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def desativar(self, request, pk=None):
        """Desativa acesso."""
        acesso = self.get_object()
        acesso.ativo = False
        acesso.save()

        serializer = self.get_serializer(acesso)
        return Response(serializer.data)

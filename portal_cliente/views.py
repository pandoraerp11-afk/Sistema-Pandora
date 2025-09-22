from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets

from core.utils import get_current_tenant
from shared.services.permission_resolver import PermissionResolver

from .models import ContaCliente, DocumentoPortalCliente
from .serializers import ContaClienteSerializer, DocumentoPortalClienteSerializer


class ContaClienteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ContaClienteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["ativo", "cliente"]
    search_fields = ["cliente__nome", "usuario__username", "usuario__email"]
    ordering = ["-data_concessao"]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        # Admin staff ou permissão específica vê todas
        if self.request.user.is_staff or PermissionResolver.resolve(
            user=self.request.user, permission="portal_cliente.view_contacliente", tenant=tenant
        ):
            return (
                ContaCliente.objects.filter(cliente__tenant=tenant)
                .select_related("cliente", "usuario")
                .order_by("-data_concessao", "id")
            )
        # Usuário normal: suas contas ativas
        return (
            ContaCliente.objects.filter(usuario=self.request.user, ativo=True, cliente__tenant=tenant)
            .select_related("cliente", "usuario")
            .order_by("-data_concessao", "id")
        )


class DocumentoPortalClienteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DocumentoPortalClienteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["ativo", "conta"]
    search_fields = ["titulo_externo", "descricao_externa", "documento_versao__documento__tipo__nome"]
    ordering = ["-created_at"]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        contas_ids = list(
            ContaCliente.objects.filter(usuario=self.request.user, ativo=True, cliente__tenant=tenant).values_list(
                "id", flat=True
            )
        )
        qs = DocumentoPortalCliente.objects.filter(
            conta_id__in=contas_ids, ativo=True, documento_versao__status="aprovado"
        ).select_related("documento_versao__documento__tipo", "conta")
        # Apenas visíveis e não expirados
        docs = [doc for doc in qs if doc.esta_visivel()]
        # ordenar por created_at desc depois id para estabilidade
        return sorted(docs, key=lambda d: (d.created_at, d.id), reverse=True)

    def list(self, request, *args, **kwargs):  # Sobrescreve para lista manual (qs vira lista)
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

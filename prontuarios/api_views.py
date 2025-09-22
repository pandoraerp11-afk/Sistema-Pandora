from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.models import TenantUser
from core.utils import get_current_tenant

from .models import Anamnese, Atendimento, FotoEvolucao, PerfilClinico
from .serializers import (
    AnamneseSerializer,
    AtendimentoSerializer,
    FotoEvolucaoSerializer,
    PerfilClinicoSerializer,
)


def _is_secretaria(user):
    """Heurística simples: usuário staff com grupo ou role contendo 'secretaria'.
    Pode ser substituído por permissão específica futuramente.
    """
    if not user.is_authenticated:
        return False
    nome_lower = {g.name.lower() for g in user.groups.all()}
    if any("secretaria" in n for n in nome_lower):
        return True
    # Checar roles via related tenant memberships se existir atributo
    for memb in getattr(user, "tenant_memberships", []).all() if hasattr(user, "tenant_memberships") else []:
        if memb.role and "secretaria" in memb.role.name.lower():
            return True
    return False


# PacienteViewSet removido – modelo consolidado em Cliente.

# Todos endpoints relacionados a procedimentos foram removidos; usar módulo 'servicos'.


class AtendimentoViewSet(viewsets.ModelViewSet):
    # Necessário para o router inferir basename; filtragem real acontece em get_queryset
    queryset = Atendimento.objects.all().order_by("-data_atendimento", "-id")
    serializer_class = AtendimentoSerializer

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = Atendimento.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        if _is_secretaria(user):
            return qs
        # Profissional só vê seus atendimentos; cliente (não staff) será tratado via futura regra
        return qs.filter(profissional=user)

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        user = self.request.user
        if not tenant:
            raise PermissionDenied("Tenant inválido")
        serializer.save(
            tenant=tenant,
            profissional=user if not user.is_superuser else serializer.validated_data.get("profissional", user),
            origem_agendamento=("CLIENTE" if (not user.is_staff and not user.is_superuser) else "PROFISSIONAL"),
        )
        # A criação/atualização de evento de agenda agora é responsabilidade do módulo 'agendamentos'
        # através do sinal post_save do modelo Agendamento.
        # atendimento.criar_ou_atualizar_evento_agenda()

    def perform_update(self, serializer):
        self.get_object()
        serializer.save()
        # A criação/atualização de evento de agenda agora é responsabilidade do módulo 'agendamentos'
        # atendimento.criar_ou_atualizar_evento_agenda()

    def perform_destroy(self, instance):
        # A lógica de cancelamento de evento de agenda foi movida para o service de Agendamentos
        return super().perform_destroy(instance)


class FotoEvolucaoViewSet(viewsets.ModelViewSet):
    queryset = FotoEvolucao.objects.all().order_by("-data_foto", "-id")
    serializer_class = FotoEvolucaoSerializer

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = FotoEvolucao.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs.order_by("-data_foto", "-id")
        # Se usuário é profissional (staff) mostra suas fotos
        if user.is_staff:
            return qs.filter(atendimento__profissional=user).order_by("-data_foto", "-id")
        # Caso seja cliente com acesso, filtrar pelas fotos associadas a atendimentos do seu cliente
        cliente_ids = getattr(user, "acessos_cliente", None)
        if cliente_ids:
            ids = [ac.cliente_id for ac in user.acessos_cliente.all()]
            return qs.filter(cliente_id__in=ids).order_by("-data_foto", "-id")
        # Nenhum acesso
        return qs.none()

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        if not tenant:
            raise PermissionDenied("Tenant inválido")
        serializer.save(tenant=tenant)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def reprocessar(self, request, pk=None):
        """Reprocessa derivados (thumbnail, webp, poster) para a foto selecionada."""
        foto = self.get_object()
        from .tasks import reprocessar_derivados_foto

        forcar = request.data.get("forcar") == "1"
        reprocessar_derivados_foto.delay(foto.id, forcar)
        return Response({"status": "agendado", "forcar": forcar})


class AnamneseViewSet(viewsets.ModelViewSet):
    queryset = Anamnese.objects.all().order_by("id")
    serializer_class = AnamneseSerializer

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = Anamnese.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(profissional_responsavel=user)

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        user = self.request.user
        if not tenant:
            raise PermissionDenied("Tenant inválido")
        serializer.save(
            tenant=tenant,
            profissional_responsavel=user
            if not user.is_superuser
            else serializer.validated_data.get("profissional_responsavel", user),
        )


class PerfilClinicoViewSet(viewsets.ModelViewSet):
    # Adiciona queryset explícito para evitar AssertionError do router quando
    # tenta inferir basename (alguns ambientes exigem atributo queryset ou basename manual).
    queryset = PerfilClinico.objects.all().order_by("id")
    serializer_class = PerfilClinicoSerializer

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = PerfilClinico.objects.filter(tenant=tenant)
        # Perfis clínicos são dados sensíveis: se não for superuser, retorna apenas perfis ligados a atendimentos do profissional
        user = self.request.user
        if user.is_superuser:
            return qs
        atend_clientes_ids = Atendimento.objects.filter(
            tenant=tenant, profissional=user, cliente__isnull=False
        ).values_list("cliente_id", flat=True)
        return qs.filter(cliente_id__in=atend_clientes_ids)

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        if not tenant:
            raise PermissionDenied("Tenant inválido")
        serializer.save(tenant=tenant)


"""Endpoints de Slots/Disponibilidades removidos deste módulo. A gestão está centralizada em Agendamentos."""


# Quick-create de paciente removido.

## Endpoint quick_create_procedimento (legado) removido após migração para Servico/ServicoClinico.


# === Endpoints de busca para Select2 (Cliente, Serviço, Profissional) ===
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def search_clientes(request):
    """Retorna lista reduzida de clientes do tenant atual para uso com Select2.
    Query params: q (texto), page (1-based), page_size (default 20), tipo (PF/PJ opcional)
    Response: [{id, text}]
    """
    tenant = get_current_tenant(request)
    if not tenant:
        return Response([], status=200)
    try:
        from clientes.models import Cliente
    except Exception:
        return Response([], status=200)
    q = (request.query_params.get("q") or "").strip()
    tipo = request.query_params.get("tipo")
    page = int(request.query_params.get("page") or 1)
    page_size = int(request.query_params.get("page_size") or 20)
    qs = Cliente.objects.filter(tenant=tenant, status="active")
    if tipo in ("PF", "PJ"):
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(
            Q(pessoafisica__nome_completo__icontains=q)
            | Q(pessoajuridica__razao_social__icontains=q)
            | Q(pessoajuridica__nome_fantasia__icontains=q)
            | Q(email__icontains=q)
            | Q(telefone__icontains=q)
        )
    offset = (page - 1) * page_size
    items = []
    for c in qs.select_related("pessoafisica", "pessoajuridica").order_by("-id")[offset : offset + page_size]:
        doc = c.documento_principal or ""
        text = f"{c.nome_display}" + (f" · {doc}" if doc else "")
        items.append({"id": c.id, "text": text})
    return Response({"results": items, "pagination": {"more": qs.count() > offset + page_size}})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def search_profissionais(request):
    """Busca profissionais (usuários vinculados ao tenant) para Select2.
    Padrão: staff_only = True (retorna apenas profissionais). Envie staff_only=0 para incluir todos.
    Suporta q, page, page_size.
    """
    tenant = get_current_tenant(request)
    if not tenant:
        return Response([], status=200)
    get_user_model()
    q = (request.query_params.get("q") or "").strip()
    page = int(request.query_params.get("page") or 1)
    page_size = int(request.query_params.get("page_size") or 20)
    # Por padrão mantemos apenas profissionais; staff_only=0 expande para todos
    staff_only_param = request.query_params.get("staff_only")
    staff_only = True if staff_only_param is None else (staff_only_param == "1")
    tu_qs = TenantUser.objects.filter(tenant=tenant).select_related("user")
    if staff_only:
        # Heurística de profissional: is_staff OU grupos contendo 'secretaria'/'prof' OU username iniciando com 'prof'
        from django.db.models import Q as _Q

        tu_qs = tu_qs.filter(
            _Q(user__is_staff=True)
            | _Q(user__groups__name__icontains="secretaria")
            | _Q(user__groups__name__icontains="prof")
            | _Q(user__username__istartswith="prof")
        ).distinct()
    if q:
        tu_qs = tu_qs.filter(
            Q(user__username__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
        )
    offset = (page - 1) * page_size
    itens = []
    for tu in tu_qs.order_by("user__first_name", "user__last_name", "user__username")[offset : offset + page_size]:
        u = tu.user
        nome = (u.get_full_name() or u.username).strip()
        itens.append({"id": u.id, "text": nome})
    return Response({"results": itens, "pagination": {"more": tu_qs.count() > offset + page_size}})


# === Upload Mobile Foto Evolução ===
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def upload_foto_evolucao_mobile(request):
    """Endpoint rápido para upload de foto via app mobile / câmera.
    Campos esperados multipart: imagem, atendimento (id), tipo_foto, momento, area_fotografada, titulo(opc), observacoes(opc)
    Restringe acesso: profissional responsável pelo atendimento OU (futuro) paciente do atendimento.
    """
    tenant = get_current_tenant(request)
    if not tenant:
        return Response({"detail": "tenant inválido"}, status=400)
    user = request.user
    atendimento_id = request.POST.get("atendimento")
    if not atendimento_id:
        return Response({"detail": "atendimento requerido"}, status=400)
    try:
        atendimento = Atendimento.objects.select_related("profissional", "cliente").get(
            id=atendimento_id, tenant=tenant
        )
    except Atendimento.DoesNotExist:
        return Response({"detail": "atendimento não encontrado"}, status=404)
    # Permissão: superuser, profissional dono; (paciente futuro: comparar user->cliente)
    if not (user.is_superuser or atendimento.profissional_id == user.id):
        return Response({"detail": "sem permissão"}, status=403)
    imagem = request.FILES.get("imagem")
    if not imagem:
        return Response({"detail": "imagem requerida"}, status=400)
    from .models import FotoEvolucao

    foto = FotoEvolucao.objects.create(
        tenant=tenant,
        cliente=atendimento.cliente,
        atendimento=atendimento,
        titulo=request.POST.get("titulo") or f"Auto {atendimento.id}",
        tipo_foto=request.POST.get("tipo_foto") or "GERAL",
        momento=request.POST.get("momento") or "ACOMPANHAMENTO",
        area_fotografada=request.POST.get("area_fotografada") or "Geral",
        imagem=imagem,
        data_foto=request.POST.get("data_foto") or atendimento.data_atendimento,
        observacoes=request.POST.get("observacoes", ""),
        visivel_cliente=True,
    )
    ser = FotoEvolucaoSerializer(foto, context={"request": request})
    return Response(ser.data, status=201)

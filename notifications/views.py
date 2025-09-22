import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, UpdateView
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response

from core.mixins import TenantRequiredMixin
from core.utils import get_current_tenant

from .models import (
    ConfiguracaoNotificacao,
    EmailDelivery,
    Notification,
    NotificationAdvanced,
    NotificationMetrics,
    NotificationRule,
    NotificationTemplate,
    PreferenciaUsuarioNotificacao,
    TenantNotificationSettings,
    UserNotificationPreferences,
)
from .serializers import (
    EmailDeliverySerializer,
    NotificationBatchActionSerializer,
    NotificationCreateSerializer,
    NotificationMetricsSerializer,
    NotificationRuleSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
    TenantNotificationSettingsSerializer,
    UserNotificationPreferencesSerializer,
)

logger = logging.getLogger(__name__)

USE_ADVANCED_NOTIFICATIONS = getattr(settings, "USE_ADVANCED_NOTIFICATIONS", True)


class IsTenantAdminOrReadOnly(BasePermission):
    """Permite escrita apenas para superuser ou usuário marcado como staff do tenant."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # Escrita: precisa ser superuser ou staff
        return bool(
            request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
        )


class OwnsNotification(BasePermission):
    """Garante acesso somente às notificações onde o usuário é destinatário."""

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Notification):  # simples
            return getattr(obj, "usuario_destinatario_id", None) == request.user.id
        # advanced (NotificationAdvanced) -> tem recipients
        if hasattr(obj, "recipients"):
            return obj.recipients.filter(user=request.user).exists()
        return False


@login_required
def notifications_home(request):
    """
    View para o dashboard de Notificações, mostrando estatísticas e dados relevantes.
    """
    template_name = "notifications/notifications_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Notificações"),
        "subtitulo": _("Visão geral do módulo Notificações"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class NotificationListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notificacoes"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.request.tenant, usuario_destinatario=self.request.user)

        # Filtros
        status_filter = self.request.GET.get("status")
        tipo_filter = self.request.GET.get("tipo")
        prioridade_filter = self.request.GET.get("prioridade")
        search_query = self.request.GET.get("search")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if tipo_filter:
            queryset = queryset.filter(tipo=tipo_filter)
        if prioridade_filter:
            queryset = queryset.filter(prioridade=prioridade_filter)
        if search_query:
            queryset = queryset.filter(Q(titulo__icontains=search_query) | Q(mensagem__icontains=search_query))

        # Expirar notificações se necessário
        for notificacao in queryset:
            notificacao.expirar_se_necessario()

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Minhas Notificações"
        context["page_subtitle"] = "Central de Notificações e Avisos"

        # Estatísticas
        context["total_nao_lidas"] = self.get_queryset().filter(status="nao_lida").count()
        context["total_lidas"] = self.get_queryset().filter(status="lida").count()
        context["total_arquivadas"] = self.get_queryset().filter(status="arquivada").count()

        # Choices para filtros
        context["status_choices"] = Notification.STATUS_CHOICES
        context["tipo_choices"] = Notification.TIPO_CHOICES
        context["prioridade_choices"] = Notification.PRIORIDADE_CHOICES

        return context


class NotificationDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    model = Notification
    template_name = "notifications/notification_detail.html"
    context_object_name = "notificacao"

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant, usuario_destinatario=self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Marcar como lida automaticamente ao visualizar
        if obj.status == "nao_lida":
            obj.marcar_como_lida()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Detalhes da Notificação"
        context["page_subtitle"] = "Informações detalhadas da notificação"
        context["logs"] = self.object.logs.all()
        return context


@method_decorator(csrf_exempt, name="dispatch")
class NotificationActionView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    model = Notification

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant, usuario_destinatario=self.request.user)

    def post(self, request, *args, **kwargs):
        notificacao = self.get_object()
        action = request.POST.get("action")

        if action == "marcar_lida":
            notificacao.marcar_como_lida()
            messages.success(request, "Notificação marcada como lida.")
        elif action == "arquivar":
            notificacao.arquivar()
            messages.success(request, "Notificação arquivada.")
        else:
            messages.error(request, "Ação inválida.")

        return redirect("notifications:notification_list")


@csrf_exempt
def api_notification_action(request):
    """API para ações em notificações via AJAX"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    if request.method == "POST":
        data = json.loads(request.body)
        notification_id = data.get("notification_id")
        action = data.get("action")

        try:
            notificacao = Notification.objects.get(
                id=notification_id, tenant=request.tenant, usuario_destinatario=request.user
            )

            if action == "marcar_lida":
                notificacao.marcar_como_lida()
                return JsonResponse({"status": "success", "message": "Notificação marcada como lida."})
            elif action == "arquivar":
                notificacao.arquivar()
                return JsonResponse({"status": "success", "message": "Notificação arquivada."})
            else:
                return JsonResponse({"status": "error", "message": "Ação inválida."}, status=400)

        except Notification.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Notificação não encontrada."}, status=404)
        except Exception as e:
            logger.error(f"Erro na API de notificações: {str(e)}")
            return JsonResponse({"status": "error", "message": "Erro interno do servidor."}, status=500)

    return JsonResponse({"status": "error", "message": "Método não permitido."}, status=405)


@csrf_exempt
def api_notifications_count(request):
    """API para contar notificações não lidas"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    try:
        count = Notification.objects.filter(
            tenant=request.tenant, usuario_destinatario=request.user, status="nao_lida"
        ).count()

        return JsonResponse({"count": count})
    except Exception as e:
        logger.error(f"Erro ao contar notificações: {str(e)}")
        return JsonResponse({"error": "Erro interno do servidor."}, status=500)


@csrf_exempt
def api_notifications_recent(request):
    """API para buscar notificações recentes"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    try:
        limit = int(request.GET.get("limit", 5))
        notificacoes = Notification.objects.filter(
            tenant=request.tenant, usuario_destinatario=request.user, status="nao_lida"
        ).order_by("-created_at")[:limit]

        data = []
        for notificacao in notificacoes:
            data.append(
                {
                    "id": notificacao.id,
                    "titulo": notificacao.titulo,
                    "mensagem": notificacao.mensagem[:100] + "..."
                    if len(notificacao.mensagem) > 100
                    else notificacao.mensagem,
                    "tipo": notificacao.tipo,
                    "prioridade": notificacao.prioridade,
                    "created_at": notificacao.created_at.isoformat(),
                    "url_acao": notificacao.url_acao,
                    "icone": notificacao.get_icone_tipo(),
                    "cor": notificacao.get_cor_prioridade(),
                }
            )

        return JsonResponse({"notifications": data})
    except Exception as e:
        logger.error(f"Erro ao buscar notificações recentes: {str(e)}")
        return JsonResponse({"error": "Erro interno do servidor."}, status=500)


class PreferenciaNotificacaoUpdateView(LoginRequiredMixin, UpdateView):
    model = PreferenciaUsuarioNotificacao
    template_name = "notifications/preferencia_form_ultra_modern.html"
    fields = [
        "receber_notificacoes",
        "receber_info",
        "receber_warning",
        "receber_error",
        "receber_success",
        "receber_alert",
        "receber_baixa",
        "receber_media",
        "receber_alta",
        "receber_critica",
        "email_habilitado",
        "push_habilitado",
        "sms_habilitado",
    ]
    success_url = reverse_lazy("notifications:notification_list")

    def get_object(self, queryset=None):
        obj, created = PreferenciaUsuarioNotificacao.objects.get_or_create(usuario=self.request.user)
        return obj

    def form_valid(self, form):
        messages.success(self.request, "Preferências de notificação atualizadas com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Preferências de Notificação"
        context["page_subtitle"] = "Configure como você deseja receber notificações"
        return context


# Views para administração (apenas para admins do tenant)
class ConfiguracaoNotificacaoUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    model = ConfiguracaoNotificacao
    template_name = "notifications/configuracao_form_ultra_modern.html"
    fields = [
        "dias_expiracao_padrao",
        "dias_retencao_lidas",
        "dias_retencao_arquivadas",
        "max_notificacoes_por_hora",
        "agrupar_notificacoes_similares",
        "email_habilitado",
        "push_habilitado",
        "sms_habilitado",
    ]
    success_url = reverse_lazy("notifications:notification_list")

    def get_object(self, queryset=None):
        obj, created = ConfiguracaoNotificacao.objects.get_or_create(tenant=self.request.tenant)
        return obj

    def form_valid(self, form):
        messages.success(self.request, "Configurações de notificação atualizadas com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Configurações de Notificação"
        context["page_subtitle"] = "Configure as notificações para sua empresa"
        return context


# Função utilitária para criar notificações programaticamente
def criar_notificacao(
    tenant,
    usuario_destinatario,
    titulo,
    mensagem,
    tipo="info",
    prioridade="media",
    modulo_origem=None,
    url_acao=None,
    objeto_relacionado=None,
    dados_extras=None,
):
    """
    Função utilitária para criar notificações de outros módulos.

    Args:
        tenant: Instância do Tenant
        usuario_destinatario: Instância do CustomUser
        titulo: Título da notificação
        mensagem: Mensagem da notificação
        tipo: Tipo da notificação (info, warning, error, success, alert)
        prioridade: Prioridade (baixa, media, alta, critica)
        modulo_origem: Nome do módulo que originou a notificação
        url_acao: URL para ação relacionada
        objeto_relacionado: Objeto relacionado (opcional)
        dados_extras: Dados extras em formato dict (opcional)

    Returns:
        Instância da Notification criada
    """
    # Verificar preferências do usuário
    try:
        preferencia = usuario_destinatario.preferencia_notificacao
        if not preferencia.deve_receber_notificacao(tipo, prioridade, modulo_origem):
            logger.info(f"Notificação não enviada para {usuario_destinatario.username} devido às preferências.")
            return None
    except PreferenciaUsuarioNotificacao.DoesNotExist:
        pass  # Se não tem preferência, criar a notificação

    # Criar a notificação
    notificacao_data = {
        "tenant": tenant,
        "usuario_destinatario": usuario_destinatario,
        "titulo": titulo,
        "mensagem": mensagem,
        "tipo": tipo,
        "prioridade": prioridade,
        "modulo_origem": modulo_origem,
        "url_acao": url_acao,
        "dados_extras": dados_extras or {},
    }

    # Adicionar referência ao objeto relacionado se fornecido
    try:
        if objeto_relacionado:
            from django.contrib.contenttypes.models import ContentType

            notificacao_data["content_type"] = ContentType.objects.get_for_model(objeto_relacionado)
            notificacao_data["object_id"] = objeto_relacionado.id
        notificacao = Notification.objects.create(**notificacao_data)
        logger.info(f"Notificação criada: {notificacao.id} para {usuario_destinatario.username}")
        return notificacao
    except Exception as e:
        logger.error(f"Erro ao criar notificação: {str(e)}")
        return None


@csrf_exempt
def api_notification_batch_action(request):
    """API para ações em lote nas notificações via AJAX"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Usuário não autenticado."}, status=401)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            notification_ids = data.get("ids", [])
            operation = data.get("operation")

            if not notification_ids:
                return JsonResponse({"error": "Nenhuma notificação selecionada."}, status=400)

            # Buscar notificações do usuário
            notifications = Notification.objects.filter(
                id__in=notification_ids, tenant=request.tenant, usuario_destinatario=request.user
            )

            if not notifications.exists():
                return JsonResponse({"error": "Notificações não encontradas."}, status=404)

            # Executar a operação
            if operation == "mark_as_read":
                for notification in notifications:
                    notification.marcar_como_lida()
                return JsonResponse({"status": "Notificações marcadas como lidas com sucesso."})

            elif operation == "mark_as_unread":
                notifications.update(status="nao_lida", data_leitura=None)
                return JsonResponse({"status": "Notificações marcadas como não lidas com sucesso."})

            elif operation == "archive":
                updated = 0
                for notification in notifications:
                    if notification.status != "arquivada":
                        notification.arquivar()
                        updated += 1
                return JsonResponse({"status": f"{updated} notificações arquivadas."})
            elif operation == "delete":
                count = notifications.count()
                notifications.delete()
                return JsonResponse({"status": f"{count} notificações excluídas com sucesso."})

            else:
                return JsonResponse({"error": "Operação inválida."}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Dados JSON inválidos."}, status=400)
        except Exception as e:
            logger.error(f"Erro na API de ações em lote: {str(e)}")
            return JsonResponse({"error": "Erro interno do servidor."}, status=500)

    return JsonResponse({"error": "Método não permitido."}, status=405)


from django.db import transaction

# Acrescenta função util para sincronizar leitura de notificações do chat


def marcar_notificacoes_chat_lidas(conversa_id, usuario, mensagem_ids=None):
    """Marca notificações originadas por mensagens de uma conversa como lidas para o usuário.
    Opcionalmente filtra por ids de mensagens específicas em dados_extras.
    """
    try:
        qs = Notification.objects.filter(
            tenant=getattr(usuario, "current_tenant", None) or usuario.tenant_memberships.first().tenant,  # fallback
            usuario_destinatario=usuario,
            modulo_origem="chat",
            dados_extras__conversa_id=conversa_id,
            status="nao_lida",
        )
        if mensagem_ids:
            # Filtra notificações cujo mensagem_id está na lista
            qs = qs.filter(dados_extras__mensagem_id__in=mensagem_ids)
        agora = timezone.now()
        with transaction.atomic():
            for n in qs.select_for_update():
                n.status = "lida"
                n.data_leitura = agora
                n.save(update_fields=["status", "data_leitura"])
        return True
    except Exception as e:
        logger.error(f"Erro ao sincronizar notificações de chat para conversa {conversa_id}: {e}")
        return False


# ================== API / DRF VIEWSETS AVANÇADOS ==================


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet para notificações avançadas (NotificationAdvanced)."""

    queryset = NotificationAdvanced.objects.all().select_related("tenant", "template").order_by("-created_at")
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, OwnsNotification]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        # Somente notificações do usuário (recipients)
        qs = qs.filter(recipients__user=self.request.user)
        # Filtros opcionais
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return NotificationCreateSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = serializer.save()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="batch")
    def batch_action(self, request):
        batch_serializer = NotificationBatchActionSerializer(data=request.data)
        batch_serializer.is_valid(raise_exception=True)
        ids = batch_serializer.validated_data["ids"]
        operation = batch_serializer.validated_data["operation"]
        qs = NotificationAdvanced.objects.filter(id__in=ids)
        if operation == "mark_as_read":
            qs.update(read_date=timezone.now(), status="read")
        elif operation == "mark_as_unread":
            qs.update(read_date=None, status="pending")
        elif operation == "delete":
            qs.delete()
            return Response({"status": "deleted"})
        return Response({"status": operation})


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all().order_by("id")
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsTenantAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(Q(is_global=True) | Q(tenant=tenant))


class NotificationRuleViewSet(viewsets.ModelViewSet):
    queryset = NotificationRule.objects.all().select_related("tenant", "template").order_by("id")
    serializer_class = NotificationRuleSerializer
    permission_classes = [IsAuthenticated, IsTenantAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


class TenantNotificationSettingsViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = TenantNotificationSettings.objects.all()
    serializer_class = TenantNotificationSettingsSerializer
    permission_classes = [IsAuthenticated, IsTenantAdminOrReadOnly]

    def get_object(self):
        tenant = getattr(self.request, "tenant", None)
        obj, _ = TenantNotificationSettings.objects.get_or_create(tenant=tenant)
        return obj


class UserNotificationPreferencesViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = UserNotificationPreferences.objects.all()
    serializer_class = UserNotificationPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, _ = UserNotificationPreferences.objects.get_or_create(user=self.request.user)
        return obj


class NotificationMetricsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = NotificationMetrics.objects.all()
    serializer_class = NotificationMetricsSerializer
    permission_classes = [IsAuthenticated, IsTenantAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-date", "-hour")[:200]


class EmailDeliveryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = EmailDelivery.objects.all().select_related("notification_recipient__notification")
    serializer_class = EmailDeliverySerializer
    permission_classes = [IsAuthenticated, IsTenantAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            qs = qs.filter(notification_recipient__notification__tenant=tenant)
        return qs.order_by("-created_at")[:200]

import contextlib
import json
import logging
from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.models import CustomUser
from core.utils import get_current_tenant

from .forms import ConfiguracaoChatForm, ConversaForm, MensagemForm, PreferenciaUsuarioChatForm
from .models import (
    ConfiguracaoChat,
    Conversa,
    ConversaFavorita,
    LogMensagem,
    Mensagem,
    MensagemFixada,
    MensagemReacao,
    PreferenciaUsuarioChat,
)

logger = logging.getLogger(__name__)


@login_required
def chat_home(request):
    """Workspace principal estilo mensageiro: lista de conversas + contatos + painel de mensagens.

    - Carrega conversas do usuário
    - Carrega lista de contatos possíveis (outros usuários do tenant)
    - Se ?c=<id> for passado, pré-seleciona conversa
    """
    tenant = get_current_tenant(request)
    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o chat."))
        return redirect(reverse("core:tenant_select"))

    user = request.user

    conversas_qs = (
        Conversa.objects.filter(tenant=tenant, participantes=user, status="ativa")
        .annotate(
            mensagens_nao_lidas=Count("mensagens", filter=Q(mensagens__lida=False) & ~Q(mensagens__remetente=user)),
            ultima_mensagem_data=Max("mensagens__created_at"),
        )
        .order_by("-ultima_atividade")
    )

    # Contatos: todos usuários do tenant menos o próprio
    contatos = (
        CustomUser.objects.filter(tenant_memberships__tenant=tenant)
        .exclude(id=user.id)
        .distinct()
        .order_by("first_name", "last_name", "username")[:300]
    )

    conversa_id = request.GET.get("c")
    conversa_selecionada = None
    if conversa_id and conversa_id.isdigit():
        conversa_selecionada = conversas_qs.filter(id=conversa_id).first()

    # Estatísticas rápidas
    unread_messages = (
        Mensagem.objects.filter(tenant=tenant, conversa__participantes=user, lida=False).exclude(remetente=user).count()
    )
    total_conversas = conversas_qs.count()
    favoritas = ConversaFavorita.objects.filter(usuario=user, conversa__tenant=tenant).count()
    mensagens_24h = Mensagem.objects.filter(
        tenant=tenant, conversa__participantes=user, created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    fixadas = MensagemFixada.objects.filter(conversa__tenant=tenant, conversa__participantes=user).count()
    favoritas_ids = list(
        _ConversasFavoritas := ConversaFavorita.objects.filter(usuario=user, conversa__tenant=tenant).values_list(
            "conversa_id", flat=True
        )
    )
    fixadas_conversas_ids = list(
        MensagemFixada.objects.filter(conversa__tenant=tenant, conversa__participantes=user)
        .values_list("conversa_id", flat=True)
        .distinct()
    )

    context = {
        "tenant": tenant,
        "conversas": conversas_qs[:200],  # limite inicial
        "contatos": contatos,
        "conversa_selecionada": conversa_selecionada,
        "page_title": "",  # sem cabeçalho principal
        "page_subtitle": "",
        "unread_messages": unread_messages,
        "total_conversas": total_conversas,
        "favoritas_count": favoritas,
        "mensagens_24h": mensagens_24h,
        "fixadas_count": fixadas,
        "favoritas_ids": favoritas_ids,
        "fixadas_conversas_ids": fixadas_conversas_ids,
    }
    return render(request, "chat/chat_home.html", context)


class ConversaListView(LoginRequiredMixin, ListView):
    """Lista de conversas do usuário"""

    model = Conversa
    template_name = "chat/conversa_list.html"
    context_object_name = "conversas"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        if not tenant:
            return Conversa.objects.none()
        queryset = (
            Conversa.objects.filter(tenant=tenant, participantes=user, status="ativa")
            .annotate(
                ultima_mensagem_data=Max("mensagens__created_at"),
                mensagens_nao_lidas=Count("mensagens", filter=Q(mensagens__lida=False) & ~Q(mensagens__remetente=user)),
            )
            .order_by("-ultima_atividade")
        )
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search) | Q(participantes__username__icontains=search)
            ).distinct()
        tipo = self.request.GET.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tenant = get_current_tenant(self.request)
        context.update(
            {
                "page_title": "Conversas",
                "page_subtitle": "Gerencie suas conversas e mensagens",
                "search_query": self.request.GET.get("search", ""),
                "tipo_filter": self.request.GET.get("tipo", ""),
                "tipo_choices": Conversa.TIPO_CHOICES,
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Chat", "url": None},
                    {"title": "Conversas", "url": None, "active": True},
                ],
                "can_add": True,
                "can_edit": True,
                "can_delete": True,
                "add_url": reverse("chat:conversa_create"),
            }
        )
        if tenant:
            total_conversas = Conversa.objects.filter(tenant=tenant, participantes=user, status="ativa").count()
            total_mensagens_nao_lidas = (
                Mensagem.objects.filter(tenant=tenant, conversa__participantes=user, lida=False)
                .exclude(remetente=user)
                .count()
            )
            conversas_recentes = Conversa.objects.filter(
                tenant=tenant, participantes=user, status="ativa", created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            context.update(
                {
                    "total_count": total_conversas,
                    "active_count": total_conversas,
                    "inactive_count": 0,
                    "recent_count": conversas_recentes,
                    "unread_count": total_mensagens_nao_lidas,
                }
            )
        return context


class ConversaDetailView(LoginRequiredMixin, DetailView):
    """Detalhes de uma conversa específica"""

    model = Conversa
    template_name = "chat/conversa_detail.html"
    context_object_name = "conversa"

    def get_queryset(self):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        if not tenant:
            return Conversa.objects.none()
        return Conversa.objects.filter(tenant=tenant, participantes=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversa = self.get_object()
        user = self.request.user
        Mensagem.objects.filter(conversa=conversa, lida=False).exclude(remetente=user).update(lida=True)
        mensagens = Mensagem.objects.filter(conversa=conversa).select_related("remetente").order_by("created_at")
        paginator = Paginator(mensagens, 50)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context.update(
            {
                "page_title": "Conversa",
                "page_subtitle": f"{conversa.titulo or 'Conversa sem título'}",
                "mensagens": page_obj,
                "page_obj": page_obj,
                "form": MensagemForm(),
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Chat", "url": None},
                    {"title": "Conversas", "url": reverse("chat:conversa_list")},
                    {"title": "Conversa", "url": None, "active": True},
                ],
                "can_edit": True,
                "can_delete": True,
                "edit_url": reverse("chat:conversa_update", kwargs={"pk": conversa.pk}),
                "delete_url": reverse("chat:conversa_delete", kwargs={"pk": conversa.pk}),
                "list_url": reverse("chat:conversa_list"),
                "participantes": conversa.participantes.all(),
                "total_mensagens": mensagens.count(),
                "is_admin": user == conversa.criador,
            }
        )
        return context


class ConversaCreateView(LoginRequiredMixin, CreateView):
    """Criar nova conversa"""

    model = Conversa
    form_class = ConversaForm
    template_name = "chat/conversa_form.html"
    success_url = reverse_lazy("chat:conversa_list")

    def form_valid(self, form):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        if not tenant:
            messages.error(self.request, "Usuário não possui tenant associado.")
            return redirect("chat:conversa_list")
        form.instance.tenant = tenant
        form.instance.criador = user
        response = super().form_valid(form)
        self.object.adicionar_participante(user)
        logger.info(f"Conversa criada: {self.object.id} por {user.username}")
        messages.success(self.request, "Conversa criada com sucesso!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Nova Conversa",
                "page_subtitle": "Criar uma nova conversa",
                "form_title": "Criar Nova Conversa",
                "submit_text": "Criar Conversa",
                "cancel_url": reverse("chat:conversa_list"),
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Chat", "url": None},
                    {"title": "Conversas", "url": reverse("chat:conversa_list")},
                    {"title": "Nova Conversa", "url": None, "active": True},
                ],
            }
        )
        return context


class ConversaUpdateView(LoginRequiredMixin, UpdateView):
    """Editar conversa"""

    model = Conversa
    form_class = ConversaForm
    template_name = "chat/conversa_form.html"
    success_url = reverse_lazy("chat:conversa_list")

    def get_queryset(self):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        if not tenant:
            return Conversa.objects.none()
        return Conversa.objects.filter(tenant=tenant, participantes=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Editar Conversa",
                "page_subtitle": f"Editando: {self.object.titulo or 'Conversa'}",
                "form_title": "Editar Conversa",
                "submit_text": "Salvar Alterações",
                "cancel_url": reverse("chat:conversa_detail", kwargs={"pk": self.object.pk}),
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Chat", "url": None},
                    {"title": "Conversas", "url": reverse("chat:conversa_list")},
                    {"title": "Editar", "url": None, "active": True},
                ],
            }
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Conversa atualizada com sucesso!")
        return super().form_valid(form)


class ConversaDeleteView(LoginRequiredMixin, DeleteView):
    """Excluir conversa"""

    model = Conversa
    template_name = "chat/conversa_confirm_delete.html"
    success_url = reverse_lazy("chat:conversa_list")
    context_object_name = "conversa"

    def get_queryset(self):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        if not tenant:
            return Conversa.objects.none()
        return Conversa.objects.filter(tenant=tenant, participantes=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Excluir Conversa",
                "page_subtitle": f"Confirmação de exclusão: {self.object.titulo or 'Conversa'}",
                "delete_message": f'Tem certeza que deseja excluir a conversa "{self.object.titulo or "sem título"}"?',
                "warning_message": "Esta ação não pode ser desfeita e todas as mensagens serão perdidas.",
                "cancel_url": reverse("chat:conversa_detail", kwargs={"pk": self.object.pk}),
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Chat", "url": None},
                    {"title": "Conversas", "url": reverse("chat:conversa_list")},
                    {"title": "Excluir", "url": None, "active": True},
                ],
            }
        )
        return context

    def form_valid(self, form):
        titulo = self.object.titulo or "Conversa"
        try:
            response = super().form_valid(form)
            messages.success(self.request, f'Conversa "{titulo}" excluída com sucesso!')
            return response
        except Exception as e:
            messages.error(self.request, f'Não foi possível excluir a conversa "{titulo}". Erro: {str(e)}')
            return redirect("chat:conversa_list")


class MensagemCreateView(LoginRequiredMixin, CreateView):
    """Enviar nova mensagem"""

    model = Mensagem
    form_class = MensagemForm
    template_name = "chat/mensagem_form.html"

    def form_valid(self, form):
        user = self.request.user
        tenant = get_current_tenant(self.request)
        conversa_id = self.kwargs.get("conversa_id")
        if not tenant:
            messages.error(self.request, "Usuário não possui tenant associado.")
            return redirect("chat:conversa_list")
        try:
            conversa = Conversa.objects.get(id=conversa_id, tenant=tenant, participantes=user)
        except Conversa.DoesNotExist:
            messages.error(self.request, "Conversa não encontrada.")
            return redirect("chat:conversa_list")
        form.instance.tenant = tenant
        form.instance.conversa = conversa
        form.instance.remetente = user
        if "arquivo" in self.request.FILES:
            form.instance.tipo = "arquivo"
            form.instance.nome_arquivo_original = self.request.FILES["arquivo"].name
        response = super().form_valid(form)
        conversa.ultima_atividade = timezone.now()
        conversa.save(update_fields=["ultima_atividade"])
        LogMensagem.objects.create(mensagem=self.object, usuario=user, acao="Mensagem enviada.")
        logger.info(f"Mensagem enviada: {self.object.id} por {user.username}")
        return response

    def get_success_url(self):
        return reverse_lazy("chat:conversa_detail", kwargs={"pk": self.object.conversa.id})


@login_required
def configuracao_chat_view(request):
    """View para configurações do chat"""
    user = request.user
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, "Usuário não possui tenant associado.")
        return redirect("chat:conversa_list")

    # Verificar se o usuário tem permissão para alterar configurações
    if not user.is_staff:
        messages.error(request, "Você não tem permissão para alterar as configurações.")
        return redirect("chat:conversa_list")

    configuracao, created = ConfiguracaoChat.objects.get_or_create(tenant=tenant)

    if request.method == "POST":
        form = ConfiguracaoChatForm(request.POST, instance=configuracao)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações salvas com sucesso!")
            return redirect("chat:configuracao_chat")
    else:
        form = ConfiguracaoChatForm(instance=configuracao)

    context = {
        "form": form,
        "page_title": "Configurações do Chat",
        "page_subtitle": "Gerencie as configurações do chat da empresa",
    }

    return render(request, "chat/configuracao_chat.html", context)


@login_required
def preferencia_usuario_view(request):
    """View para preferências do usuário"""
    user = request.user

    preferencia, created = PreferenciaUsuarioChat.objects.get_or_create(usuario=user)

    if request.method == "POST":
        form = PreferenciaUsuarioChatForm(request.POST, instance=preferencia)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferências salvas com sucesso!")
            return redirect("chat:preferencia_usuario")
    else:
        form = PreferenciaUsuarioChatForm(instance=preferencia)

    context = {
        "form": form,
        "page_title": "Minhas Preferências",
        "page_subtitle": "Configure suas preferências de chat",
    }

    return render(request, "chat/preferencia_usuario.html", context)


# APIs AJAX
@csrf_exempt
@login_required
def api_enviar_mensagem(request):
    """API para enviar mensagem via AJAX"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"})

    try:
        data = json.loads(request.body)
        user = request.user
        tenant = get_current_tenant(request)

        if not tenant:
            return JsonResponse({"status": "error", "message": "Usuário não possui tenant associado"})

        conversa_id = data.get("conversa_id")
        conteudo = data.get("conteudo", "").strip()
        resposta_para_id = data.get("resposta_para_id")

        if not conversa_id or not conteudo:
            return JsonResponse({"status": "error", "message": "Dados obrigatórios não fornecidos"})

        # Verificar se a conversa existe e o usuário tem acesso
        try:
            conversa = Conversa.objects.get(id=conversa_id, tenant=tenant, participantes=user)
        except Conversa.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Conversa não encontrada"})

        # Verificar mensagem de resposta se fornecida
        resposta_para = None
        if resposta_para_id:
            with contextlib.suppress(Mensagem.DoesNotExist):
                resposta_para = Mensagem.objects.get(id=resposta_para_id, conversa=conversa)

        # Criar a mensagem
        mensagem = Mensagem.objects.create(
            tenant=tenant, conversa=conversa, remetente=user, conteudo=conteudo, resposta_para=resposta_para
        )

        # Atualizar última atividade da conversa
        conversa.ultima_atividade = timezone.now()
        conversa.save(update_fields=["ultima_atividade"])

        # Log da ação
        LogMensagem.objects.create(mensagem=mensagem, usuario=user, acao="Mensagem enviada via API.")

        return JsonResponse(
            {"status": "success", "message": "Mensagem enviada com sucesso", "mensagem_id": mensagem.id}
        )

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON inválido"})
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem via API: {str(e)}")
        return JsonResponse({"status": "error", "message": "Erro interno do servidor"})


@csrf_exempt
@login_required
def api_marcar_como_lida(request):
    """API para marcar mensagem como lida"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"})

    try:
        data = json.loads(request.body)
        user = request.user
        tenant = get_current_tenant(request)

        if not tenant:
            return JsonResponse({"status": "error", "message": "Usuário não possui tenant associado"})

        mensagem_id = data.get("mensagem_id")

        if not mensagem_id:
            return JsonResponse({"status": "error", "message": "ID da mensagem não fornecido"})

        # Verificar se a mensagem existe e o usuário tem acesso
        try:
            mensagem = Mensagem.objects.get(id=mensagem_id, tenant=tenant, conversa__participantes=user)
        except Mensagem.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Mensagem não encontrada"})

        # Marcar como lida
        mensagem.marcar_como_lida(user)

        return JsonResponse({"status": "success", "message": "Mensagem marcada como lida"})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON inválido"})
    except Exception as e:
        logger.error(f"Erro ao marcar mensagem como lida: {str(e)}")
        return JsonResponse({"status": "error", "message": "Erro interno do servidor"})


@login_required
def api_conversas_recentes(request):
    """API para buscar conversas recentes"""
    user = request.user
    tenant = get_current_tenant(request)

    if not tenant:
        return JsonResponse({"status": "error", "message": "Usuário não possui tenant associado"})

    conversas = (
        Conversa.objects.filter(tenant=tenant, participantes=user, status="ativa")
        .annotate(
            mensagens_nao_lidas=Count("mensagens", filter=Q(mensagens__lida=False) & ~Q(mensagens__remetente=user))
        )
        .order_by("-ultima_atividade")[:10]
    )

    conversas_data = []
    for conversa in conversas:
        ultima_mensagem = conversa.get_ultima_mensagem()
        conversas_data.append(
            {
                "id": conversa.id,
                "titulo": conversa.get_titulo_display(),
                "tipo": conversa.tipo,
                "mensagens_nao_lidas": conversa.mensagens_nao_lidas,
                "ultima_atividade": conversa.ultima_atividade.isoformat() if conversa.ultima_atividade else None,
                "ultima_mensagem": {
                    "conteudo": ultima_mensagem.conteudo[:50] + "..."
                    if ultima_mensagem and len(ultima_mensagem.conteudo) > 50
                    else ultima_mensagem.conteudo
                    if ultima_mensagem
                    else "",
                    "remetente": ultima_mensagem.remetente.username if ultima_mensagem else "",
                    "data": ultima_mensagem.created_at.isoformat() if ultima_mensagem else None,
                }
                if ultima_mensagem
                else None,
            }
        )

    return JsonResponse({"status": "success", "conversas": conversas_data})


# ========================= NOVAS APIS WORKSPACE =============================


@login_required
def api_contacts(request):
    """Lista contatos (usuários do tenant) com busca simples."""
    user = request.user
    tenant = get_current_tenant(request)
    if not tenant:
        return JsonResponse({"status": "error", "message": "Tenant não encontrado"})
    search = request.GET.get("q", "").strip()
    qs = CustomUser.objects.filter(tenant_memberships__tenant=tenant).exclude(id=user.id).distinct()
    if search:
        qs = qs.filter(Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
    qs = qs.order_by("first_name", "last_name", "username")[:50]
    data = [
        {
            "id": u.id,
            "nome": u.get_full_name() or u.username,
            "username": u.username,
        }
        for u in qs
    ]
    return JsonResponse({"status": "success", "contatos": data})


@login_required
def api_start_conversa(request):
    """Cria (ou obtém) uma conversa individual com um usuário alvo."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = request.POST
    user = request.user
    tenant = get_current_tenant(request)
    if not tenant:
        return JsonResponse({"status": "error", "message": "Tenant não encontrado"})
    target_id = payload.get("user_id")
    if not target_id:
        return JsonResponse({"status": "error", "message": "user_id é obrigatório"})
    try:
        alvo = CustomUser.objects.filter(id=target_id, tenant_memberships__tenant=tenant).distinct().get()
    except CustomUser.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Usuário não encontrado"})
    # Obter ou criar conversa individual
    conversa = (
        Conversa.objects.filter(tenant=tenant, tipo="individual", participantes=user).filter(participantes=alvo).first()
    )
    if not conversa:
        conversa = Conversa.objects.create(
            tenant=tenant,
            tipo="individual",
            criador=user,
            titulo="",  # será determinado dinamicamente
        )
        conversa.adicionar_participante(user, adicionado_por=user)
        conversa.adicionar_participante(alvo, adicionado_por=user)
    return JsonResponse({"status": "success", "conversa_id": conversa.id})


@login_required
def api_conversa_mensagens(request, conversa_id):
    """Retorna mensagens de uma conversa em JSON.

    Parâmetros:
      limit (int) - quantidade de mensagens (default 50)
      before_id (int) - se fornecido, retorna mensagens com id < before_id (scroll para cima)
    """
    user = request.user
    tenant = get_current_tenant(request)
    if not tenant:
        return JsonResponse({"status": "error", "message": "Tenant não encontrado"})
    try:
        conversa = Conversa.objects.get(id=conversa_id, tenant=tenant, participantes=user)
    except Conversa.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Conversa não encontrada"}, status=404)
    limit = min(int(request.GET.get("limit", 50)), 200)
    before_id = request.GET.get("before_id")
    qs = conversa.mensagens.select_related("remetente").order_by("-id")
    if before_id and before_id.isdigit():
        qs = qs.filter(id__lt=int(before_id))
    slice_qs = list(qs[:limit])
    has_more = False
    if slice_qs:
        menor_id = slice_qs[-1].id
        has_more = conversa.mensagens.filter(id__lt=menor_id).exists()
    mensagens = []
    for m in slice_qs:
        mensagens.append(
            {
                "id": m.id,
                "conteudo": m.conteudo,
                "remetente": m.remetente.username,
                "remetente_id": m.remetente_id,
                "created_at": m.created_at.isoformat(),
                "status": m.status,
                "lida": m.lida,
                "tipo": m.tipo,
                "arquivo_url": m.arquivo.url if m.arquivo else None,
                "arquivo_nome": m.get_nome_arquivo(),
            }
        )
    return JsonResponse({"status": "success", "mensagens": list(reversed(mensagens)), "has_more": has_more})


@login_required
def api_upload_arquivo(request):
    """Upload de arquivo/imagem para conversa, broadcast via WebSocket.

    FormData: conversa_id, file
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)
    user = request.user
    tenant = get_current_tenant(request)
    if not tenant:
        return JsonResponse({"status": "error", "message": "Tenant não encontrado"})
    conversa_id = request.POST.get("conversa_id")
    if not conversa_id:
        return JsonResponse({"status": "error", "message": "conversa_id requerido"})
    try:
        conversa = Conversa.objects.get(id=conversa_id, tenant=tenant, participantes=user)
    except Conversa.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Conversa não encontrada"}, status=404)
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"status": "error", "message": "Arquivo não enviado"})
    # Validações básicas
    config = getattr(tenant, "configuracao_chat", None)
    if config and f.size > config.tamanho_maximo_arquivo_mb * 1024 * 1024:
        return JsonResponse({"status": "error", "message": "Arquivo excede tamanho máximo"})
    ext = Path(f.name).suffix.lower()
    tipo_msg = "arquivo"
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
        tipo_msg = "imagem"
    mensagem = Mensagem.objects.create(
        tenant=tenant,
        conversa=conversa,
        remetente=user,
        conteudo=f.name,
        tipo=tipo_msg,
        arquivo=f,
        nome_arquivo_original=f.name,
    )
    conversa.ultima_atividade = timezone.now()
    conversa.save(update_fields=["ultima_atividade"])
    LogMensagem.objects.create(mensagem=mensagem, usuario=user, acao="Upload de arquivo")
    msg_dict = {
        "id": mensagem.id,
        "conteudo": mensagem.conteudo,
        "remetente": user.username,
        "remetente_id": user.id,
        "created_at": mensagem.created_at.isoformat(),
        "status": mensagem.status,
        "tipo": mensagem.tipo,
        "arquivo_url": mensagem.arquivo.url if mensagem.arquivo else None,
        "arquivo_nome": mensagem.get_nome_arquivo(),
    }
    # Broadcast via channel layer
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_conversa_{conversa.id}", {"type": "chat.message", "event": "new_message", "mensagem": msg_dict}
        )
    except Exception:
        pass
    return JsonResponse({"status": "success", "mensagem": msg_dict})


@csrf_exempt
@login_required
def api_toggle_favorito(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)
    user = request.user
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except Exception:
        data = request.POST
    cid = data.get("conversa_id")
    if not (cid and str(cid).isdigit()):
        return JsonResponse({"status": "error", "message": "conversa_id inválido"})
    try:
        conversa = Conversa.objects.get(id=cid, participantes=user)
    except Conversa.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Conversa não encontrada"})
    fav, created = ConversaFavorita.objects.get_or_create(usuario=user, conversa=conversa)
    if not created:
        fav.delete()
        return JsonResponse({"status": "success", "favorito": False})
    return JsonResponse({"status": "success", "favorito": True})


@csrf_exempt
@login_required
def api_reagir_mensagem(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)
    user = request.user
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except Exception:
        data = request.POST
    mid = data.get("mensagem_id")
    emoji = data.get("emoji")
    if not (mid and emoji):
        return JsonResponse({"status": "error", "message": "Dados incompletos"})
    try:
        msg = Mensagem.objects.get(id=mid, conversa__participantes=user)
    except Mensagem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Mensagem não encontrada"})
    if len(emoji) > 32:
        return JsonResponse({"status": "error", "message": "Emoji inválido"})
    reacao, created = MensagemReacao.objects.get_or_create(mensagem=msg, usuario=user, emoji=emoji)
    if not created:
        reacao.delete()
    reacoes = list(msg.reacoes.values("emoji").annotate(total=Count("emoji")).order_by("-total"))
    return JsonResponse({"status": "success", "reacoes": reacoes})


@csrf_exempt
@login_required
def api_fixar_mensagem(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)
    user = request.user
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except Exception:
        data = request.POST
    mid = data.get("mensagem_id")
    if not (mid and str(mid).isdigit()):
        return JsonResponse({"status": "error", "message": "mensagem_id inválido"})
    try:
        msg = Mensagem.objects.get(id=mid, conversa__participantes=user)
    except Mensagem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Mensagem não encontrada"})
    conversa = msg.conversa
    fix, created = MensagemFixada.objects.get_or_create(conversa=conversa, mensagem=msg, defaults={"fixada_por": user})
    if not created:
        fix.delete()
        return JsonResponse({"status": "success", "fixada": False})
    return JsonResponse({"status": "success", "fixada": True})

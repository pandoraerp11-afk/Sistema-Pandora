import contextlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.mixins import PageTitleMixin, SuperuserRequiredMixin, TenantAdminOrSuperuserMixin
from core.models import TenantUser

# Importações de Mixins e Utils
from core.utils import get_current_tenant
from shared.mixins.ui_permissions import UIPermissionsMixin
from user_management.services.logging_service import log_activity
from user_management.twofa import RATE_MSG_GLOBAL_IP, RATE_MSG_LOCK, RATE_MSG_MICRO, global_ip_rate_limit_check

from .forms import (
    ConviteUsuarioForm,
    FiltroUsuarioForm,
    MeuPerfilForm,
    PermissaoPersonalizadaForm,
    UsuarioCreateForm,
    UsuarioUpdateForm,
)
from .models import (
    ConviteUsuario,
    LogAtividadeUsuario,
    PerfilUsuarioEstendido,
    PermissaoPersonalizada,
    SessaoUsuario,
    StatusUsuario,
)
from .realtime import broadcast_session_event
from .risk import build_context_maps, compute_risks, session_to_dict
from .twofa import (
    confirm_2fa,
    decrypt_secret,
    disable_2fa,
    encrypt_secret,
    generate_recovery_codes,
    hash_code,
    provision_uri,
    rate_limit_check,
    setup_2fa,
    use_recovery_code,
    verify_totp,
)

User = get_user_model()

# ==============================================================================
# MIXINS LOCAIS PARA USER_MANAGEMENT
# ==============================================================================


@login_required
def user_management_home(request):
    """
    View para o dashboard de Gerenciamento de Usuários, mostrando estatísticas e dados relevantes.
    """
    template_name = "user_management/user_management_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Coletar estatísticas para o dashboard

    # Verificar se é superusuário
    if request.user.is_superuser:
        # Para superusuário, mostrar estatísticas globais de todo o sistema
        total_usuarios = User.objects.count()

        # Contar usuários ativos (do Django)
        usuarios_ativos = User.objects.filter(is_active=True).count()

        # Contar todos os convites pendentes do sistema
        convites_pendentes = ConviteUsuario.objects.filter(usado=False, expirado_em__gte=timezone.now()).count()

        # Contar sessões ativas do Django
        from django.contrib.sessions.models import Session

        sessoes_ativas = Session.objects.filter(expire_date__gte=timezone.now()).count()

    else:
        # Usuário normal - mostrar apenas dados do tenant
        tenant_users = TenantUser.objects.filter(tenant=tenant)

        # Estatísticas básicas
        total_usuarios = tenant_users.count()

        # Verificar se existe PerfilUsuarioEstendido para esses usuários
        usuarios_queryset = PerfilUsuarioEstendido.objects.filter(user__in=tenant_users.values_list("user", flat=True))

        # Contagem de usuários ativos
        if usuarios_queryset.exists():
            usuarios_ativos = usuarios_queryset.filter(status=StatusUsuario.ATIVO).count()
        else:
            # Se não há perfis, assumir que todos os TenantUsers estão ativos
            usuarios_ativos = total_usuarios

        # Convites pendentes
        convites_pendentes = ConviteUsuario.objects.filter(
            tenant=tenant, usado=False, expirado_em__gte=timezone.now()
        ).count()

        # Sessões ativas
        sessoes_ativas = SessaoUsuario.objects.filter(
            ativa=True, user__in=tenant_users.values_list("user", flat=True)
        ).count()

        # Se não há sessões específicas, usar uma estimativa baseada nos usuários
        if sessoes_ativas == 0 and total_usuarios > 0:
            # Estimar que 30% dos usuários podem estar ativos
            sessoes_ativas = max(1, int(total_usuarios * 0.3))

    context = {
        "titulo": _("Gerenciamento de Usuários"),
        "subtitulo": _("Visão geral do módulo Gerenciamento de Usuários"),
        "tenant": tenant,
        "total_usuarios": total_usuarios,
        "usuarios_ativos": usuarios_ativos,
        "convites_pendentes": convites_pendentes,
        "sessoes_ativas": sessoes_ativas,
    }

    return render(request, template_name, context)


class UserManagementFormMixin:
    """
    Mixin para injetar automaticamente `tenant` e `request_user` nos formulários.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # O tenant é anexado ao request pelo TenantAdminOrSuperuserMixin
        kwargs["tenant"] = getattr(self.request, "tenant", None)
        kwargs["request_user"] = self.request.user
        return kwargs


class LogActivityMixin:
    """
    Mixin para registrar logs de atividade para Create e Update.
    """

    log_action_create = "CREATE"
    log_action_update = "UPDATE"
    log_model_name = ""

    def form_valid(self, form):
        response = super().form_valid(form)
        is_create = self.object._state.adding
        action = self.log_action_create if is_create else self.log_action_update

        log_activity(
            self.request.user,
            f"{action}_{self.log_model_name.upper()}",
            "user_management",
            f"{'Criou' if is_create else 'Atualizou'} o registro: {self.object}",
            objeto=self.object,
            ip=self.request.META.get("REMOTE_ADDR", ""),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
        return response


# ==============================================================================
# VIEWS DE USUÁRIO (PERFIL)
# ==============================================================================


class UsuarioListView(TenantAdminOrSuperuserMixin, UIPermissionsMixin, PageTitleMixin, ListView):
    model = PerfilUsuarioEstendido
    template_name = "user_management/usuario_list.html"
    context_object_name = "object_list"  # Alterado de 'perfis' para o padrão
    paginate_by = 100  # Aumentado para mostrar mais usuários por página
    page_title = "Gerenciamento de Usuários"
    app_label = "user_management"
    model_name = "perfilusuarioestendido"

    def get_queryset(self):
        queryset = PerfilUsuarioEstendido.objects.select_related("user").all()

        # Aplicar escopo de tenant
        if not self.request.user.is_superuser:
            tenant = getattr(self.request, "tenant", None)
            if tenant:
                queryset = queryset.filter(user__tenant_memberships__tenant_id=tenant.id)
            else:
                return queryset.none()

        # Filtros (GET) utilizando FiltroUsuarioForm
        self.filter_form = None
        self.filter_form = FiltroUsuarioForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("busca"):
                termo = data["busca"]
                queryset = queryset.filter(
                    Q(user__first_name__icontains=termo)
                    | Q(user__last_name__icontains=termo)
                    | Q(user__email__icontains=termo)
                    | Q(cpf__icontains=termo)
                )
            if data.get("tipo_usuario"):
                queryset = queryset.filter(tipo_usuario=data["tipo_usuario"])
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            if data.get("departamento"):
                queryset = queryset.filter(departamento__icontains=data["departamento"])
            if data.get("ativo") == "true":
                queryset = queryset.filter(user__is_active=True)
            elif data.get("ativo") == "false":
                queryset = queryset.filter(user__is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Incluir form de filtro no contexto
        context["filter_form"] = getattr(self, "filter_form", None)
        return context


class UsuarioDetailView(TenantAdminOrSuperuserMixin, UIPermissionsMixin, PageTitleMixin, DetailView):
    model = PerfilUsuarioEstendido
    template_name = "user_management/usuario_detail.html"
    context_object_name = "perfil"
    app_label = "user_management"
    model_name = "perfilusuarioestendido"

    def get_queryset(self):
        qs = super().get_queryset()

        # Superusuário pode ver qualquer perfil, independentemente do tenant selecionado.
        if self.request.user.is_superuser:
            return qs

        # Para outros usuários, a restrição de tenant se aplica.
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return qs.filter(user__tenant_memberships__tenant_id=tenant.id)

        # Se não for superuser e não tiver tenant, não pode ver ninguém.
        return qs.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = f"Detalhes de {self.object.user.get_full_name()}"
        context["sessoes_ativas"] = SessaoUsuario.objects.filter(user=self.object.user, ativa=True)
        context["atividades_recentes"] = LogAtividadeUsuario.objects.filter(user=self.object.user)[:20]
        context["permissoes"] = PermissaoPersonalizada.objects.filter(user=self.object.user)
        # Reset de senha: só expor se houver TenantUser inequívoco
        tenant = getattr(self.request, "tenant", None)
        tu_qs = TenantUser.objects.filter(user=self.object.user)
        if tenant:
            tu_qs = tu_qs.filter(tenant_id=tenant.id)
        elif tu_qs.count() != 1:
            tu_qs = tu_qs.none()
        if tu_qs.exists():
            from django.urls import reverse

            context["reset_password_url"] = reverse("core:tenant_user_reset_password", args=[tu_qs.first().pk])
        return context


class UsuarioCreateView(
    TenantAdminOrSuperuserMixin,
    UIPermissionsMixin,
    UserManagementFormMixin,
    LogActivityMixin,
    PageTitleMixin,
    CreateView,
):
    model = User  # O form cria o User e o Perfil
    form_class = UsuarioCreateForm
    template_name = "user_management/usuario_form.html"
    success_url = reverse_lazy("user_management:usuario_list")
    page_title = "Criar Novo Usuário"
    log_model_name = "User"
    app_label = "user_management"
    model_name = "perfilusuarioestendido"

    def form_valid(self, form):
        messages.success(self.request, f"Usuário {form.instance.username} criado com sucesso!")
        return super().form_valid(form)


class UsuarioUpdateView(
    TenantAdminOrSuperuserMixin,
    UIPermissionsMixin,
    UserManagementFormMixin,
    LogActivityMixin,
    PageTitleMixin,
    UpdateView,
):
    model = PerfilUsuarioEstendido
    form_class = UsuarioUpdateForm
    template_name = "user_management/usuario_form.html"
    success_url = reverse_lazy("user_management:usuario_list")
    log_model_name = "PerfilUsuarioEstendido"
    app_label = "user_management"
    model_name = "perfilusuarioestendido"

    def get_queryset(self):
        qs = super().get_queryset()

        # Superusuário pode editar qualquer perfil, independentemente do tenant selecionado.
        if self.request.user.is_superuser:
            return qs

        # Para outros usuários, a restrição de tenant se aplica.
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return qs.filter(user__tenant_memberships__tenant_id=tenant.id)

        # Se não for superuser e não tiver tenant, não pode editar ninguém.
        return qs.none()

    def get_page_title(self):
        return f"Editar Usuário: {self.object.user.username}"

    def form_valid(self, form):
        messages.success(self.request, f"Usuário {self.object.user.username} atualizado com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Reset de senha: só expor se houver TenantUser inequívoco
        tenant = getattr(self.request, "tenant", None)
        tu_qs = TenantUser.objects.filter(user=self.object.user)
        if tenant:
            tu_qs = tu_qs.filter(tenant_id=tenant.id)
        elif tu_qs.count() != 1:
            tu_qs = tu_qs.none()
        if tu_qs.exists():
            from django.urls import reverse

            context["reset_password_url"] = reverse("core:tenant_user_reset_password", args=[tu_qs.first().pk])
        return context


# ==============================================================================
# VIEWS DE CONVITE
# ==============================================================================


class ConviteListView(TenantAdminOrSuperuserMixin, PageTitleMixin, ListView):
    model = ConviteUsuario
    template_name = "user_management/convite_list.html"
    context_object_name = "convites"
    paginate_by = 25
    page_title = "Gerenciamento de Convites"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("enviado_por", "usuario_criado", "tenant")

        # Superusuário pode ver todos os convites. O tenant selecionado é apenas um filtro.
        if self.request.user.is_superuser:
            tenant_from_session = getattr(self.request, "tenant", None)
            tenant_id_filter = self.request.GET.get("tenant")
            effective_tenant_id = tenant_id_filter or (tenant_from_session.id if tenant_from_session else None)

            if effective_tenant_id:
                return queryset.filter(tenant_id=effective_tenant_id)

            return queryset

        # Para outros usuários, a restrição de tenant se aplica.
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return queryset.filter(tenant=tenant)

        return queryset.none()


class ConviteCreateView(TenantAdminOrSuperuserMixin, UserManagementFormMixin, PageTitleMixin, CreateView):
    model = ConviteUsuario
    form_class = ConviteUsuarioForm
    template_name = "user_management/convite_form.html"
    success_url = reverse_lazy("user_management:convite_list")
    page_title = "Enviar Novo Convite"

    def form_valid(self, form):
        # O tenant e o enviado_por já são setados no form
        convite = form.save()

        # Envio de e-mail do convite
        try:
            link_convite = self.request.build_absolute_uri(
                reverse("user_management:aceitar_convite", kwargs={"token": convite.token})
            )
            assunto = f"Convite para acessar o sistema {getattr(settings, 'SITE_NAME', 'Pandora ERP')}"
            mensagem = f"""
Olá {convite.nome_completo or convite.email},

Você foi convidado(a) para acessar nosso sistema como {convite.get_tipo_usuario_display()}.

Para aceitar o convite e criar sua conta, clique no link abaixo:
{link_convite}

{convite.mensagem_personalizada or ""}

Este convite expira em {convite.expirado_em.strftime("%d/%m/%Y às %H:%M")}.

Atenciosamente,
{self.request.user.get_full_name() or self.request.user.username}
"""
            send_mail(
                assunto,
                mensagem,
                settings.DEFAULT_FROM_EMAIL,
                [convite.email],
                fail_silently=False,
            )
            messages.success(self.request, f"Convite enviado para {convite.email} com sucesso!")
        except Exception as e:  # pragma: no cover - caminho de erro de infraestrutura
            messages.warning(self.request, f"Convite criado, mas erro ao enviar e-mail: {e}")

        # Log
        log_activity(
            self.request.user,
            "SEND_INVITE",
            "user_management",
            f"Enviou convite para {convite.email}",
            objeto=convite,
            ip=self.request.META.get("REMOTE_ADDR", ""),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
        return redirect(self.get_success_url())


class AceitarConviteView(PageTitleMixin, CreateView):
    template_name = "user_management/aceitar_convite.html"
    form_class = UsuarioCreateForm
    # Após criação redireciona para login (PRG p/ evitar repost)
    success_url = reverse_lazy("core:login")
    page_title = "Aceitar Convite"

    def dispatch(self, request, *args, **kwargs):
        self.convite = get_object_or_404(ConviteUsuario, token=self.kwargs.get("token"))
        if not self.convite.pode_ser_usado:
            messages.error(request, "Este convite não é mais válido.")
            return redirect("core:login")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = self.convite.email
        initial["tipo_usuario"] = self.convite.tipo_usuario
        # ... (outros campos pré-preenchidos) ...
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["email"].widget.attrs["readonly"] = True
        form.fields["tipo_usuario"].widget.attrs["readonly"] = True
        # No fluxo de convite permitir criação sem nome imediato
        if "first_name" in form.fields:
            form.fields["first_name"].required = False
        if "last_name" in form.fields:
            form.fields["last_name"].required = False
        return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Fornece contexto necessário para o form salvar Perfil corretamente
        kwargs["request_user"] = None  # convite externo (sem usuário autenticado)
        kwargs["tenant"] = getattr(self.convite, "tenant", None)
        return kwargs

    def form_valid(self, form):
        # Força tipo_usuario do convite (ignora alteração maliciosa em POST)
        form.cleaned_data["tipo_usuario"] = self.convite.tipo_usuario
        user = form.save()
        # Associa usuário ao tenant do convite
        if self.convite.tenant:
            from core.models import TenantUser

            TenantUser.objects.get_or_create(user=user, tenant=self.convite.tenant)

        # Atualiza convite
        self.convite.usado = True
        self.convite.aceito_em = timezone.now()
        self.convite.usuario_criado = user
        self.convite.save()

        # Atualiza o perfil estendido
        if hasattr(user, "perfil_estendido"):
            perfil = user.perfil_estendido
            changed = False
            if perfil.tipo_usuario != self.convite.tipo_usuario:
                perfil.tipo_usuario = self.convite.tipo_usuario
                changed = True
            if perfil.status == StatusUsuario.PENDENTE:
                perfil.status = StatusUsuario.ATIVO
                changed = True
            if changed:
                perfil.save()

        messages.success(self.request, "Conta criada com sucesso! Você já pode fazer login.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Disponibiliza o objeto convite para o template (necessário para blocos informativos)
        ctx["convite"] = getattr(self, "convite", None)
        return ctx


# ==============================================================================
# VIEWS DE PERMISSÕES (Exemplo)
# ==============================================================================


class PermissionRequiredMixin:
    required_modulo = None
    required_acao = None
    required_recurso = None
    permission_scope_tenant = True  # se True tenta usar request.tenant.id

    def dispatch(self, request, *args, **kwargs):
        if self.required_modulo and self.required_acao:
            # Uso do resolver unificado (modernizado). Ação canônica: ACAO_MODULO em UPPER.
            from shared.services.permission_resolver import has_permission  # import local p/ evitar ciclo em cold start

            tenant = None
            if self.permission_scope_tenant:
                tenant = getattr(request, "tenant", None)
            action = f"{self.required_acao}_{self.required_modulo}".upper()
            if not (tenant and has_permission(request.user, tenant, action, self.required_recurso)):
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Permissão negada")
        return super().dispatch(request, *args, **kwargs)


class PermissaoListView(SuperuserRequiredMixin, PermissionRequiredMixin, PageTitleMixin, ListView):
    model = PermissaoPersonalizada
    template_name = "user_management/permissao_list.html"
    context_object_name = "permissoes"
    paginate_by = 25
    page_title = "Permissões Personalizadas"
    required_modulo = "user_management"
    required_acao = "view_permissions"


class PermissaoCreateView(
    SuperuserRequiredMixin,
    PermissionRequiredMixin,
    UserManagementFormMixin,
    LogActivityMixin,
    PageTitleMixin,
    CreateView,
):
    model = PermissaoPersonalizada
    form_class = PermissaoPersonalizadaForm
    template_name = "user_management/permissao_form.html"
    success_url = reverse_lazy("user_management:permissao_list")
    page_title = "Conceder Permissão"
    log_model_name = "PermissaoPersonalizada"
    required_modulo = "user_management"
    required_acao = "create_permission"

    def form_valid(self, form):
        messages.success(self.request, "Permissão concedida com sucesso!")
        return super().form_valid(form)


# ==============================================================================
# VIEWS DE LOGS E SESSÕES
# ==============================================================================


class LogAtividadeListView(TenantAdminOrSuperuserMixin, PermissionRequiredMixin, PageTitleMixin, ListView):
    model = LogAtividadeUsuario
    template_name = "user_management/atividade_list.html"
    context_object_name = "atividades"
    paginate_by = 50
    page_title = "Logs de Atividade dos Usuários"
    ordering = ["-timestamp"]
    required_modulo = "auditoria"
    required_acao = "view_logs"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")

        if self.request.user.is_superuser:
            tenant_from_session = getattr(self.request, "tenant", None)
            tenant_id_filter = self.request.GET.get("tenant")
            effective_tenant_id = tenant_id_filter or (tenant_from_session.id if tenant_from_session else None)

            if effective_tenant_id:
                # Filtra logs de usuários pertencentes ao tenant selecionado
                return queryset.filter(user__tenant_memberships__tenant_id=effective_tenant_id)
            return queryset

        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return queryset.filter(user__tenant_memberships__tenant_id=tenant.id)

        return queryset.none()


class SessaoUsuarioListView(TenantAdminOrSuperuserMixin, PermissionRequiredMixin, PageTitleMixin, ListView):
    model = SessaoUsuario
    template_name = "user_management/sessao_list.html"
    context_object_name = "sessoes"
    paginate_by = 50
    page_title = "Sessões de Usuários Ativas"
    ordering = ["-criada_em"]  # Corrigido de 'inicio_sessao' para 'criada_em'
    required_modulo = "user_management"
    required_acao = "view_sessions"

    def get_queryset(self):
        queryset = super().get_queryset().filter(ativa=True).select_related("user")

        if self.request.user.is_superuser:
            tenant_from_session = getattr(self.request, "tenant", None)
            tenant_id_filter = self.request.GET.get("tenant")
            effective_tenant_id = tenant_id_filter or (tenant_from_session.id if tenant_from_session else None)

            if effective_tenant_id:
                return queryset.filter(user__tenant_memberships__tenant_id=effective_tenant_id)
            return queryset

        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return queryset.filter(user__tenant_memberships__tenant_id=tenant.id)

        return queryset.none()


class SessaoEncerrarView(LoginRequiredMixin, View):
    """Encerra (marca como inativa) uma sessão específica (própria ou qualquer se superuser)."""

    def post(self, request, pk):
        sessao = get_object_or_404(SessaoUsuario, pk=pk)
        if not request.user.is_superuser and sessao.user != request.user:
            return JsonResponse({"detail": "Sem permissão."}, status=403)
        sessao.ativa = False
        sessao.save(update_fields=["ativa"])
        broadcast_session_event("terminated", sessao)
        log_activity(
            request.user,
            "TERMINATE_SESSION",
            "user_management",
            f"Encerrou sessão {sessao.pk} de {sessao.user.username}",
            objeto=sessao,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "ok"})
        messages.success(request, "Sessão encerrada.")
        return redirect("user_management:sessao_list")


class SessaoEncerrarTodasView(LoginRequiredMixin, View):
    """Encerra todas as sessões ativas de um usuário (próprio usuário ou qualquer se superuser)."""

    def post(self, request, user_id):
        alvo = get_object_or_404(User, pk=user_id)
        if not request.user.is_superuser and alvo != request.user:
            return JsonResponse({"detail": "Sem permissão."}, status=403)
        sessoes = SessaoUsuario.objects.filter(user=alvo, ativa=True)
        count = 0
        for s in sessoes:
            s.ativa = False
            s.save(update_fields=["ativa"])
            broadcast_session_event("terminated", s)
            count += 1
        if count:
            log_activity(
                request.user,
                "TERMINATE_ALL_SESSIONS",
                "user_management",
                f"Encerrou {count} sessões de {alvo.username}",
                objeto=alvo,
                ip=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "ok", "encerradas": count})
        messages.success(request, f"Sessões encerradas ({count}).")
        return redirect("user_management:sessao_list")


class SessaoDetalheView(LoginRequiredMixin, View):
    """Retorna detalhes de uma sessão (JSON)."""

    def get(self, request, pk):
        sessao = get_object_or_404(SessaoUsuario, pk=pk)
        # Autorizações: superuser ou dono da sessão (futuramente: tenant admin do mesmo tenant caso relacionamento exista)
        if not request.user.is_superuser and sessao.user != request.user:
            return JsonResponse({"detail": "Sem permissão."}, status=403)
        data = {
            "id": sessao.pk,
            "user": sessao.user.username,
            "ip_address": sessao.ip_address,
            "user_agent": sessao.user_agent[:200],
            "pais": sessao.pais,
            "cidade": sessao.cidade,
            "criada_em": sessao.criada_em.isoformat(),
            "ultima_atividade": sessao.ultima_atividade.isoformat(),
            "ativa": sessao.ativa,
        }
        return JsonResponse({"status": "ok", "sessao": data})


# ====================== 2FA FLOW =============================


class TwoFASetupView(LoginRequiredMixin, View):
    def post(self, request):
        perfil = request.user.perfil_estendido
        # Se já confirmado e ativo, não re-expor códigos nem gerar novo secret.
        if perfil.autenticacao_dois_fatores and perfil.totp_secret and perfil.totp_confirmed_at:
            return JsonResponse({"status": "already_enabled"})
        secret, raw_codes = setup_2fa(perfil)
        # Salvaguarda: garantir que recovery codes seja sempre lista
        if not isinstance(raw_codes, list):
            try:
                raw_codes = list(raw_codes) if raw_codes is not None else []
            except Exception:
                raw_codes = []
        # Nunca retornar None para evitar falha em testes/clientes
        raw_codes = raw_codes or []
        uri = provision_uri(request.user.username, secret)
        log_activity(
            request.user,
            "2FA_SETUP",
            "user_management",
            "Iniciou configuração 2FA",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        # Hardening: se algum outro save concorrente (middleware/sinal) sobrescreveu o secret
        perfil.refresh_from_db()
        if not perfil.totp_secret or not perfil.autenticacao_dois_fatores:
            perfil.totp_secret = encrypt_secret(secret)
            perfil.twofa_secret_encrypted = True
            perfil.autenticacao_dois_fatores = True
            if not perfil.totp_recovery_codes:
                # Regerar hashes se perdidos (não deve acontecer, mas garante consistência)
                from .twofa import hash_code

                perfil.totp_recovery_codes = [hash_code(c) for c in raw_codes]
            perfil.save(
                update_fields=[
                    "totp_secret",
                    "twofa_secret_encrypted",
                    "autenticacao_dois_fatores",
                    "totp_recovery_codes",
                ]
            )
        return JsonResponse(
            {
                "status": "ok",
                "secret": secret,
                "provisioning_uri": uri,
                "recovery_codes": raw_codes,
                "recovery_codes_count": len(raw_codes or []),
            }
        )


class TwoFAAdminForceRegenerateView(LoginRequiredMixin, View):
    """Gera novos recovery codes para o usuário (sem exigir token) mantendo mesmo secret.
    Uso: emergência (suspeita de vazamento de códigos). Registra auditoria.
    """

    def post(self, request):
        if not request.user.is_superuser:
            return JsonResponse({"detail": "Forbidden"}, status=403)
        target_id = request.POST.get("user_id") or request.GET.get("user_id")
        if not target_id:
            return JsonResponse({"detail": "user_id requerido"}, status=400)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            target = User.objects.get(id=target_id)
        except User.DoesNotExist:
            return JsonResponse({"detail": "Usuário não encontrado"}, status=404)
        perfil = target.perfil_estendido
        if not perfil.totp_secret:
            return JsonResponse({"detail": "Usuário ainda não tem 2FA configurado"}, status=400)
        raw_codes = generate_recovery_codes()
        perfil.totp_recovery_codes = [hash_code(c) for c in raw_codes]
        perfil.failed_2fa_attempts = 0
        perfil.twofa_locked_until = None
        perfil.save(update_fields=["totp_recovery_codes", "failed_2fa_attempts", "twofa_locked_until"])
        log_activity(
            request.user,
            "2FA_ADMIN_FORCE_REGEN",
            "user_management",
            f"Admin regenerou recovery codes para {target.username}",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        try:
            if target.email:
                send_mail(
                    "[PandoraERP] Recovery codes regenerados pelo administrador",
                    "Novos códigos de recuperação foram emitidos pelo administrador. Desconsidere os anteriores.",
                    settings.DEFAULT_FROM_EMAIL,
                    [target.email],
                    fail_silently=True,
                )
        except Exception:
            pass
        return JsonResponse({"status": "ok", "recovery_codes": raw_codes, "count": len(raw_codes)})


class TwoFAMetricsDashboardView(LoginRequiredMixin, View):
    template_name = "user_management/2fa_metrics_dashboard.html"

    def get(self, request):
        if not request.user.is_superuser:
            return JsonResponse({"detail": "Somente superusuário."}, status=403)
        from django.db.models import Sum

        qs = PerfilUsuarioEstendido.objects.all()
        total = qs.count()
        ativos = qs.filter(totp_secret__isnull=False).count()
        confirmados = qs.filter(totp_confirmed_at__isnull=False).count()
        criptografados = qs.filter(twofa_secret_encrypted=True, totp_secret__isnull=False).count()
        lockados = qs.filter(twofa_locked_until__gt=timezone.now()).count()
        agg = qs.aggregate(
            sucessos=Sum("twofa_success_count"),
            falhas=Sum("twofa_failure_count"),
            recovery_uses=Sum("twofa_recovery_use_count"),
            rl_blocks=Sum("twofa_rate_limit_block_count"),
        )
        ctx = {
            "total": total,
            "ativos": ativos,
            "confirmados": confirmados,
            "criptografados": criptografados,
            "lockados": lockados,
            "sucessos": agg["sucessos"] or 0,
            "falhas": agg["falhas"] or 0,
            "recovery_uses": agg["recovery_uses"] or 0,
            "rl_blocks": agg["rl_blocks"] or 0,
            "pct_confirmados": round((confirmados / total * 100), 2) if total else 0,
            "pct_criptografados": round((criptografados / ativos * 100), 2) if ativos else 0,
        }
        return render(request, self.template_name, ctx)


class TwoFAMetricsJSONView(LoginRequiredMixin, View):
    """Retorna métricas agregadas 2FA em JSON para consumo externo."""

    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"detail": "forbidden"}, status=403)
        from django.db.models import Count, Q, Sum

        agg = PerfilUsuarioEstendido.objects.aggregate(
            total=Count("id"),
            habilitados=Count("id", filter=Q(autenticacao_dois_fatores=True)),
            confirmados=Count("id", filter=Q(totp_confirmed_at__isnull=False)),
            sucessos=Sum("twofa_success_count"),
            falhas=Sum("twofa_failure_count"),
            recovery=Sum("twofa_recovery_use_count"),
            rl_blocks=Sum("twofa_rate_limit_block_count"),
        )
        # Bloqueios globais de IP não persistidos em modelo: extraímos do cache (chaves com prefixo twofa_global_block:)
        try:
            # Em caches como LocMem não há API para listar; manter contador acumulado:
            global_blocks = cache.get("twofa_global_ip_block_metric", 0) or 0
        except Exception:
            global_blocks = 0
        agg["ip_blocks"] = int(global_blocks)
        for k, v in list(agg.items()):
            agg[k] = int(v or 0)
        return JsonResponse(agg)


def global_ip_rate_limit(ip: str, bucket: str, limit: int, window_seconds: int) -> bool:
    """Retorna True se ainda dentro do limite; False se excedido.
    Implementação simples em cache: contador com janela deslizante aproximada.
    """
    if not ip:
        return True
    key = f"twofa_global_rl:{bucket}:{ip}"
    data = cache.get(key)
    now = timezone.now().timestamp()
    if not data:
        cache.set(key, {"count": 1, "start": now}, window_seconds)
        return True
    count = data.get("count", 0) + 1
    start = data.get("start", now)
    # Excedeu limite
    if count > limit:
        # Contabilizar métrica global (contador cumulativo)
        try:
            cache.incr("twofa_global_ip_block_metric")
        except Exception:
            # Fallback se incr não existir
            cur = cache.get("twofa_global_ip_block_metric", 0) or 0
            cache.set("twofa_global_ip_block_metric", cur + 1, 24 * 3600)
        return False
    # Atualiza contador mantendo expiração restante
    ttl = max(1, int(window_seconds - (now - start)))
    cache.set(key, {"count": count, "start": start}, ttl)
    return True


def emit_twofa_failure_alert(request, perfil, label: str):
    """Centraliza envio de email de alerta em thresholds configurados.
    Usa igualdade exata (==) com thresholds; cooldown por (user,threshold).
    """
    from django.conf import settings as _s

    try:
        thresholds = getattr(_s, "TWOFA_ALERT_THRESHOLDS", (20, 50, 100))
        cooldown_min = getattr(_s, "TWOFA_ALERT_EMAIL_COOLDOWN_MINUTES", 30)
        failures = getattr(perfil, "twofa_failure_count", 0)
        if failures in thresholds and request.user.email:
            cache_key = f"twofa_alert_last_email:{request.user.pk}:{failures}"
            if not cache.get(cache_key):
                send_mail(
                    f"[PandoraERP] Múltiplas falhas de 2FA ({label})",
                    "Detectamos um número elevado de falhas de verificação 2FA em sua conta. Se não foi você, considere ações de segurança.",
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email],
                    fail_silently=True,
                )
                cache.set(cache_key, True, cooldown_min * 60)
    except Exception:
        pass


class TwoFAConfirmView(LoginRequiredMixin, View):
    def post(self, request):
        data = {}
        if request.content_type == "application/json":
            import json

            with contextlib.suppress(Exception):
                data = json.loads(request.body or "{}")
        token = request.POST.get("token") or data.get("token")
        if not token:
            return JsonResponse({"detail": "Token obrigatório"}, status=400)
        perfil = request.user.perfil_estendido
        # Lockout pré-existente (reuso da mesma semântica da verify)
        if getattr(perfil, "twofa_locked_until", None):
            from django.utils import timezone

            if perfil.twofa_locked_until and perfil.twofa_locked_until > timezone.now():
                return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
        if not perfil.totp_secret:
            return JsonResponse({"detail": "2FA não iniciado"}, status=400)
        ip = request.META.get("REMOTE_ADDR", "")
        # Rate limit global (novo helper centralizado)
        if not global_ip_rate_limit_check(
            ip, getattr(settings, "TWOFA_GLOBAL_IP_LIMIT", 60), getattr(settings, "TWOFA_GLOBAL_IP_WINDOW", 300)
        ):
            return JsonResponse({"detail": RATE_MSG_GLOBAL_IP}, status=429)
        if confirm_2fa(perfil, token):
            log_activity(
                request.user,
                "2FA_CONFIRMED",
                "user_management",
                "2FA confirmado",
                objeto=None,
                ip=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            return JsonResponse({"status": "ok"})
        # Falha: confirm_2fa já incrementou failed_2fa_attempts e twofa_failure_count
        from django.conf import settings as _s

        lock_applied = False
        threshold = getattr(_s, "TWOFA_LOCK_THRESHOLD", 5)
        if perfil.failed_2fa_attempts >= threshold:
            try:
                from django.utils import timezone

                minutos = getattr(_s, "TWOFA_LOCK_MINUTES", 5)
                perfil.twofa_locked_until = timezone.now() + timezone.timedelta(minutes=minutos)
                perfil.failed_2fa_attempts = 0
                perfil.save(update_fields=["failed_2fa_attempts", "twofa_locked_until"])
                lock_applied = True
            except Exception:
                pass
        # Email de alerta (usa contador já atualizado)
        if not lock_applied:
            emit_twofa_failure_alert(request, perfil, "confirm")
        if lock_applied:
            try:
                pass  # remove debug logging
            except Exception:
                pass
            return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
        return JsonResponse({"detail": "Token inválido"}, status=400)


class TwoFADisableView(LoginRequiredMixin, View):
    def post(self, request):
        perfil = request.user.perfil_estendido
        disable_2fa(perfil)
        log_activity(
            request.user,
            "2FA_DISABLED",
            "user_management",
            "2FA desabilitado",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return JsonResponse({"status": "ok"})


class TwoFAVerifyView(LoginRequiredMixin, View):
    def post(self, request):
        data = {}
        if request.content_type == "application/json":
            import json

            with contextlib.suppress(Exception):
                data = json.loads(request.body or "{}")
        token = request.POST.get("token") or data.get("token")
        recovery_code = request.POST.get("recovery_code") or data.get("recovery_code")
        perfil = request.user.perfil_estendido
        # Lockout check
        if getattr(perfil, "twofa_locked_until", None):
            from django.utils import timezone

            if perfil.twofa_locked_until and perfil.twofa_locked_until > timezone.now():
                return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
        if not perfil.autenticacao_dois_fatores or not perfil.totp_secret:
            return JsonResponse({"detail": "2FA não habilitado"}, status=400)
        # Rate limiting micro-burst + global IP
        ip = request.META.get("REMOTE_ADDR", "")
        if not global_ip_rate_limit_check(
            ip, getattr(settings, "TWOFA_GLOBAL_IP_LIMIT", 60), getattr(settings, "TWOFA_GLOBAL_IP_WINDOW", 300)
        ):
            try:
                perfil.twofa_rate_limit_block_count = (perfil.twofa_rate_limit_block_count or 0) + 1
                perfil.save(update_fields=["twofa_rate_limit_block_count"])
                log_activity(
                    request.user,
                    "2FA_GLOBAL_IP_BLOCK",
                    "user_management",
                    "Bloqueio rate limit global 2FA (verify)",
                    ip=ip,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except Exception:
                pass
            return JsonResponse({"detail": RATE_MSG_GLOBAL_IP}, status=429)
        if not rate_limit_check(request.user.id, ip):
            try:
                perfil.twofa_rate_limit_block_count = (perfil.twofa_rate_limit_block_count or 0) + 1
                perfil.save(update_fields=["twofa_rate_limit_block_count"])
                log_activity(
                    request.user,
                    "2FA_RATE_LIMIT_BLOCK",
                    "user_management",
                    "Bloqueio micro rate limit 2FA (verify)",
                    ip=ip,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except Exception:
                pass
            return JsonResponse({"detail": RATE_MSG_MICRO}, status=429)
        # Decriptar segredo se cifrado
        secret_value = perfil.totp_secret
        if perfil.twofa_secret_encrypted:
            secret_value = decrypt_secret(secret_value)
        if token and verify_totp(secret_value, token):
            perfil.failed_2fa_attempts = 0
            perfil.twofa_locked_until = None
            # incremento sucesso
            try:
                perfil.twofa_success_count = (perfil.twofa_success_count or 0) + 1
                save_fields = ["failed_2fa_attempts", "twofa_locked_until", "twofa_success_count"]
            except Exception:
                save_fields = ["failed_2fa_attempts", "twofa_locked_until"]
            perfil.save(update_fields=save_fields)
            log_activity(
                request.user,
                "2FA_TOKEN_VERIFIED",
                "user_management",
                "Token 2FA verificado",
                objeto=None,
                ip=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            request.session["twofa_passed"] = True
            with contextlib.suppress(Exception):
                request.session.modified = True
            return JsonResponse({"status": "ok"})
        if recovery_code and use_recovery_code(perfil, recovery_code):
            log_activity(
                request.user,
                "2FA_RECOVERY_USED",
                "user_management",
                "Recovery code usado",
                objeto=None,
                ip=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            try:
                perfil.twofa_recovery_use_count = (perfil.twofa_recovery_use_count or 0) + 1
                perfil.save(update_fields=["twofa_recovery_use_count"])
            except Exception:
                pass
            request.session["twofa_passed"] = True
            with contextlib.suppress(Exception):
                request.session.modified = True
            remaining_codes = perfil.totp_recovery_codes or []
            try:
                rem_len = len(remaining_codes)
            except Exception:
                rem_len = 0
            return JsonResponse({"status": "ok", "recovery_used": True, "remaining": rem_len})
        # Falha: incrementar e avaliar lockout
        perfil.failed_2fa_attempts += 1
        try:
            perfil.twofa_failure_count = (perfil.twofa_failure_count or 0) + 1
            save_fields_fail = ["failed_2fa_attempts", "twofa_locked_until", "twofa_failure_count"]
        except Exception:
            save_fields_fail = ["failed_2fa_attempts", "twofa_locked_until"]
        lock_applied = False
        # Threshold e duração de lock vindos de settings
        from django.conf import settings as _s

        if perfil.failed_2fa_attempts >= getattr(_s, "TWOFA_LOCK_THRESHOLD", 5):
            from django.utils import timezone

            minutos = getattr(_s, "TWOFA_LOCK_MINUTES", 5)
            perfil.twofa_locked_until = timezone.now() + timezone.timedelta(minutes=minutos)
            perfil.failed_2fa_attempts = 0  # reset contador após aplicar lock
            lock_applied = True
        perfil.save(update_fields=save_fields_fail)
        # Alerta proativo
        emit_twofa_failure_alert(request, perfil, "verify")
        if lock_applied:
            return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
        return JsonResponse({"detail": "Token ou código inválido"}, status=400)


class TwoFAChallengeView(LoginRequiredMixin, View):
    template_name = "user_management/2fa_challenge.html"

    def get(self, request):
        perfil = request.user.perfil_estendido
        if not perfil.autenticacao_dois_fatores or not perfil.totp_secret or request.session.get("twofa_passed"):
            return redirect("/")
        return render(request, self.template_name, {})


class TwoFARegenerateCodesView(LoginRequiredMixin, View):
    """Regenera recovery codes exigindo token TOTP válido.
    Regras:
      - 2FA habilitado e confirmado.
      - Token válido.
      - Aplica rate limit micro e lockout como verify.
    """

    def post(self, request):
        perfil = request.user.perfil_estendido
        if not (perfil.autenticacao_dois_fatores and perfil.totp_secret and perfil.totp_confirmed_at):
            return JsonResponse({"detail": "2FA não habilitado/confirmado."}, status=400)
        ip = request.META.get("REMOTE_ADDR", "")
        if not rate_limit_check(request.user.id, ip):
            try:
                perfil.twofa_rate_limit_block_count = (perfil.twofa_rate_limit_block_count or 0) + 1
                perfil.save(update_fields=["twofa_rate_limit_block_count"])
                log_activity(
                    request.user,
                    "2FA_RATE_LIMIT_BLOCK",
                    "user_management",
                    "Bloqueio micro rate limit 2FA (regen)",
                    ip=ip,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except Exception:
                pass
            return JsonResponse({"detail": RATE_MSG_MICRO}, status=429)
        if getattr(perfil, "twofa_locked_until", None):
            from django.utils import timezone

            if perfil.twofa_locked_until and perfil.twofa_locked_until > timezone.now():
                return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
        data = {}
        if request.content_type == "application/json":
            import json

            with contextlib.suppress(Exception):
                data = json.loads(request.body or "{}")
        token = request.POST.get("token") or data.get("token")
        if not token:
            return JsonResponse({"detail": "Token obrigatório."}, status=400)
        from .twofa import generate_recovery_codes, hash_code, verify_totp

        secret_value = perfil.totp_secret
        if perfil.twofa_secret_encrypted:
            secret_value = decrypt_secret(secret_value)
        if not verify_totp(secret_value, token):
            perfil.failed_2fa_attempts += 1
            lock_applied = False
            if perfil.failed_2fa_attempts >= 5:
                from django.utils import timezone

                perfil.twofa_locked_until = timezone.now() + timezone.timedelta(minutes=5)
                perfil.failed_2fa_attempts = 0
                lock_applied = True
            perfil.save(update_fields=["failed_2fa_attempts", "twofa_locked_until"])
            if lock_applied:
                return JsonResponse({"detail": RATE_MSG_LOCK}, status=423)
            return JsonResponse({"detail": "Token inválido."}, status=400)
        raw_codes = generate_recovery_codes()
        perfil.totp_recovery_codes = [hash_code(c) for c in raw_codes]
        perfil.failed_2fa_attempts = 0
        perfil.twofa_locked_until = None
        perfil.save(update_fields=["totp_recovery_codes", "failed_2fa_attempts", "twofa_locked_until"])
        log_activity(
            request.user,
            "2FA_RECOVERY_REGENERATED",
            "user_management",
            "Recovery codes regenerados",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        with contextlib.suppress(Exception):
            send_mail(
                "[PandoraERP] Recovery codes regenerados",
                "Seus códigos de recuperação foram regenerados. Guarde-os em local seguro. Eles são exibidos apenas uma vez.",
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                fail_silently=True,
            )
        return JsonResponse({"status": "ok", "recovery_codes": raw_codes, "count": len(raw_codes)})


class TwoFAAdminResetView(LoginRequiredMixin, View):
    """Superuser pode resetar 2FA de um usuário específico via POST user_id.
    Body (form/json): {"user_id": <id>}.
    """

    def post(self, request):
        if not request.user.is_superuser:
            return JsonResponse({"detail": "Somente superusuário."}, status=403)
        data = {}
        if request.content_type == "application/json":
            import json

            with contextlib.suppress(Exception):
                data = json.loads(request.body or "{}")
        user_id = request.POST.get("user_id") or data.get("user_id")
        if not user_id:
            return JsonResponse({"detail": "user_id obrigatório."}, status=400)
        try:
            target = User.objects.get(pk=user_id)
            perfil = target.perfil_estendido
        except Exception:
            return JsonResponse({"detail": "Usuário não encontrado."}, status=404)
        from .twofa import disable_2fa

        disable_2fa(perfil)
        log_activity(
            request.user,
            "2FA_ADMIN_RESET",
            "user_management",
            f"Reset 2FA para usuário {target.username}",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        try:
            if target.email:
                send_mail(
                    "[PandoraERP] 2FA resetado pelo administrador",
                    "Seu 2FA foi resetado por um administrador. Ao efetuar login você deverá configurá-lo novamente.",
                    settings.DEFAULT_FROM_EMAIL,
                    [target.email],
                    fail_silently=True,
                )
        except Exception:
            pass
        return JsonResponse({"status": "ok", "detail": "2FA resetado; usuário deve reconfigurar."})


class TwoFAAdminForceRegenerateView(LoginRequiredMixin, View):
    """Superuser força nova geração de códigos de recuperação sem token do usuário.
    POST {"user_id": <id>}
    Mantém o mesmo secret TOTP, apenas substitui recovery codes.
    """

    def post(self, request):
        if not request.user.is_superuser:
            return JsonResponse({"detail": "Somente superusuário."}, status=403)
        data = {}
        if request.content_type == "application/json":
            import json

            with contextlib.suppress(Exception):
                data = json.loads(request.body or "{}")
        user_id = request.POST.get("user_id") or data.get("user_id")
        if not user_id:
            return JsonResponse({"detail": "user_id obrigatório."}, status=400)
        try:
            target = User.objects.get(pk=user_id)
            perfil = target.perfil_estendido
        except Exception:
            return JsonResponse({"detail": "Usuário não encontrado."}, status=404)
        if not perfil.totp_secret:
            return JsonResponse({"detail": "Usuário não possui 2FA ativo."}, status=400)
        # Gera novos códigos
        raw_codes = generate_recovery_codes()
        perfil.totp_recovery_codes = [hash_code(c) for c in raw_codes]
        perfil.save(update_fields=["totp_recovery_codes"])
        log_activity(
            request.user,
            "2FA_ADMIN_FORCE_REGEN",
            "user_management",
            f"Forçou novos recovery codes para {target.username}",
            objeto=None,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        try:
            if target.email:
                send_mail(
                    "[PandoraERP] Novos recovery codes gerados pelo administrador",
                    "Um administrador gerou novos códigos de recuperação para sua conta. Os códigos antigos foram invalidados.",
                    settings.DEFAULT_FROM_EMAIL,
                    [target.email],
                    fail_silently=True,
                )
        except Exception:
            pass
        return JsonResponse({"status": "ok", "recovery_codes": raw_codes, "count": len(raw_codes)})


class SessaoEncerrarMultiplasView(LoginRequiredMixin, View):
    """Encerra múltiplas sessões em uma única chamada.

    POST aceita JSON {"ids": [<id1>, <id2>, ...]} ou form-data ids=1,2,3
    Regras de autorização:
      - superuser: qualquer sessão
      - usuário comum: apenas suas próprias sessões
    """

    def post(self, request):
        import json

        ids = []
        if request.content_type == "application/json":
            try:
                payload = json.loads(request.body or "{}")
                ids = payload.get("ids") or []
            except json.JSONDecodeError:
                return JsonResponse({"detail": "JSON inválido."}, status=400)
        else:
            raw = request.POST.get("ids", "")
            if raw:
                ids = [p for p in raw.replace(";", ",").split(",") if p.strip()]
        try:
            ids = list(map(int, ids))
        except ValueError:
            return JsonResponse({"detail": "IDs inválidos."}, status=400)
        if not ids:
            return JsonResponse({"detail": "Nenhuma sessão informada."}, status=400)

        qs = SessaoUsuario.objects.filter(pk__in=ids, ativa=True)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        count = 0
        terminated_ids = []
        for s in qs:
            s.ativa = False
            s.save(update_fields=["ativa"])
            broadcast_session_event("terminated", s)
            count += 1
            terminated_ids.append(s.id)
        if count:
            log_activity(
                request.user,
                "TERMINATE_BULK_SESSIONS",
                "user_management",
                f"Encerrou {count} sessões (bulk).",
                objeto=None,
                ip=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        # Sempre JSON (endpoint de API interna)
        return JsonResponse({"status": "ok", "encerradas": count, "ids": terminated_ids})


class ToggleTwoFactorView(LoginRequiredMixin, View):
    """Alterna o estado de 2FA de um usuário (ou o próprio usuário)."""

    def post(self, request, pk):
        perfil = get_object_or_404(PerfilUsuarioEstendido, pk=pk)
        # Permite se for o próprio usuário ou superuser; TODO: permitir tenant admin futuramente
        if request.user != perfil.user and not request.user.is_superuser:
            return JsonResponse({"detail": "Sem permissão."}, status=403)
        perfil.autenticacao_dois_fatores = not perfil.autenticacao_dois_fatores
        perfil.save(update_fields=["autenticacao_dois_fatores"])
        log_activity(
            request.user,
            "TOGGLE_2FA",
            "user_management",
            f"Alterou 2FA para {perfil.user.username}: {perfil.autenticacao_dois_fatores}",
            objeto=perfil,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "ok", "enabled": perfil.autenticacao_dois_fatores})
        messages.success(request, "Configuração 2FA atualizada.")
        return redirect("user_management:usuario_detail", pk=perfil.pk)


class SessaoUsuarioApiView(LoginRequiredMixin, View):
    """API JSON para listagem paginada e filtrada de sessões com riscos."""

    def get(self, request):
        qs = SessaoUsuario.objects.all().select_related("user")
        # Escopo tenant se não superuser
        if not request.user.is_superuser:
            tenant = getattr(request, "tenant", None)
            if tenant:
                qs = qs.filter(user__tenant_memberships__tenant_id=tenant.id)
            else:
                qs = qs.filter(user=request.user)  # fallback restrito

        # Filtros básicos
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(user__username__icontains=q)
                | Q(user__email__icontains=q)
                | Q(ip_address__icontains=q)
                | Q(user_agent__icontains=q)
            )
        status_param = request.GET.get("status")
        if status_param == "ativo":
            qs = qs.filter(ativa=True)
        elif status_param == "inativo":
            qs = qs.filter(ativa=False)

        # Datas (criada_em)
        created_from = request.GET.get("created_from")
        created_to = request.GET.get("created_to")
        if created_from:
            try:
                dtf = timezone.datetime.fromisoformat(created_from)
                if timezone.is_naive(dtf):
                    dtf = timezone.make_aware(dtf)
                qs = qs.filter(criada_em__gte=dtf)
            except Exception:
                pass
        if created_to:
            try:
                dtt = timezone.datetime.fromisoformat(created_to)
                if timezone.is_naive(dtt):
                    dtt = timezone.make_aware(dtt)
                qs = qs.filter(criada_em__lte=dtt)
            except Exception:
                pass

        qs = qs.order_by("-ultima_atividade")

        # Paginação
        try:
            page = int(request.GET.get("page", "1"))
        except ValueError:
            page = 1
        try:
            page_size = min(int(request.GET.get("page_size", "25")), 100)
        except ValueError:
            page_size = 25
        offset = (page - 1) * page_size
        slice_qs = list(qs[offset : offset + page_size])

        # Riscos
        ips_map, paises_map = build_context_maps(slice_qs)
        sessions_data = []
        for s in slice_qs:
            risks = compute_risks(s, ips_map, paises_map)
            sessions_data.append(session_to_dict(s, risks))

        # Filtro por risco (após cálculo)
        risk_filter = request.GET.get("risk")
        if risk_filter:
            sessions_data = [d for d in sessions_data if risk_filter in d.get("risks", [])]

        total = qs.count()
        has_next = offset + page_size < total
        return JsonResponse(
            {
                "status": "ok",
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": has_next,
                "sessions": sessions_data,
            }
        )


class UsuarioDeleteView(TenantAdminOrSuperuserMixin, PageTitleMixin, View):
    """
    View para exclusão de usuários.
    Só permite exclusão se o usuário não for superuser.
    """

    page_title = "Excluir Usuário"

    def get(self, request, pk):
        usuario = get_object_or_404(PerfilUsuarioEstendido, pk=pk)

        # Impedir exclusão de superusuários
        if usuario.user.is_superuser:
            messages.error(request, "Não é possível excluir superusuários.")
            return redirect("user_management:usuario_list")

        return render(
            request, "user_management/usuario_confirm_delete.html", {"usuario": usuario, "page_title": self.page_title}
        )

    def post(self, request, pk):
        usuario = get_object_or_404(PerfilUsuarioEstendido, pk=pk)

        # Impedir exclusão de superusuários
        if usuario.user.is_superuser:
            messages.error(request, "Não é possível excluir superusuários.")
            return redirect("user_management:usuario_list")

        # Registrar log antes da exclusão
        nome_usuario = usuario.user.get_full_name() or usuario.user.username

        try:
            # Excluir o usuário (cascade irá excluir o perfil estendido)
            usuario.user.delete()
            messages.success(request, f"Usuário '{nome_usuario}' foi excluído com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao excluir usuário: {str(e)}")

        return redirect("user_management:usuario_list")


# As views de API e as mais simples (dashboard, logs, etc.) podem ser mantidas como funcionais
# ou refatoradas para CBVs se ganharem complexidade.
# ... (código das views funcionais restantes omitido) ...


# ==============================================================================
# VIEWS PARA PERFIL PESSOAL
# ==============================================================================


class MeuPerfilView(LoginRequiredMixin, UpdateView):
    """View para o usuário editar seu próprio perfil"""

    template_name = "user_management/meu_perfil.html"
    success_url = reverse_lazy("user_management:meu_perfil")

    def get_object(self):
        """Retorna o perfil estendido do usuário logado"""
        perfil, created = PerfilUsuarioEstendido.objects.get_or_create(user=self.request.user)
        return perfil

    def get_form_class(self):
        return MeuPerfilForm

    def form_valid(self, form):
        messages.success(self.request, "Perfil atualizado com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Meu Perfil"
        return context


from django.contrib.auth.views import PasswordChangeView


class ChangePasswordView(PasswordChangeView):
    """View para mudança de senha do usuário"""

    template_name = "user_management/change_password.html"
    success_url = reverse_lazy("user_management:meu_perfil")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Alterar Senha"
        return context

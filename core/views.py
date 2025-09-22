# core/views.py
import contextlib
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cadastros_gerais.models import ItemAuxiliar
from shared.mixins.ui_permissions import UIPermissionsMixin
from shared.services.ui_permissions import build_ui_permissions

from .forms import (
    CustomUserForm,
    DepartmentForm,
    EmpresaDocumentoVersaoCreateForm,
    ModuleConfigurationForm,
    RoleForm,
    TenantUserForm,
)
from .mixins import PageTitleMixin, SuperuserRequiredMixin, TenantAdminOrSuperuserMixin
from .models import (
    CustomUser,
    Department,
    EmpresaDocumento,
    EmpresaDocumentoVersao,
    Endereco,
    Role,
    Tenant,
    TenantUser,
)
from .utils import get_client_ip, get_current_tenant


@login_required
def core_home(request):
    """
    Dashboard do módulo CORE
    Exibe métricas e informações sobre empresas, usuários e configurações do sistema
    Acessível apenas por superusuários, exibe métricas globais do sistema.
    """
    if not request.user.is_superuser:
        messages.error(request, "Acesso negado. Apenas superusuários podem acessar este dashboard.")
        return redirect("core:login")

    try:
        # Importa o sistema de home
        from .home_system import CoreHomeSystem

        # Inicializa o sistema de home
        home_system = CoreHomeSystem(request.user)

        # Obtém todos os dados necessários
        context = home_system.get_home_context()

        # Adiciona informações extras do contexto
        context.update(
            {
                "page_title": "Home do Módulo CORE",
                "breadcrumbs_list": [{"title": "Core", "url": None}, {"title": "Home", "url": None}],
            }
        )

        return render(request, "core/core_home.html", context)

    except Exception as e:
        # Em caso de erro, renderiza dashboard com dados padrão
        messages.warning(request, f"Erro ao carregar dados do dashboard: {str(e)}")
        context = {
            "total_tenants": 0,
            "active_tenants": 0,
            "total_users": 0,
            "total_roles": 0,
            "total_departamentos": 0,
            "mrr_value": 0,
            "tenant_growth_labels": "[]",
            "tenant_growth_data": "[]",
            "tenant_status_labels": "[]",
            "tenant_status_data": "[]",
            "recent_tenants": [],
            "page_title": "Dashboard do Módulo CORE",
            "breadcrumbs_list": [{"title": "Core", "url": None}, {"title": "Dashboard", "url": None}],
        }

        return render(request, "core/core_home.html", context)


@login_required
def dashboard(request):
    """
    Dashboard principal do sistema (não específico do módulo CORE)
    Exibe visão geral da empresa selecionada com métricas de todos os módulos
    """
    # Se usuário só tem conta de portal cliente e nenhum TenantUser, redireciona para portal
    try:
        from portal_cliente.models import ContaCliente

        has_tenant_membership = Tenant.objects.filter(tenant_users__user=request.user, status="active").exists()
        if not has_tenant_membership and ContaCliente.objects.filter(usuario=request.user, ativo=True).exists():
            return redirect("portal_cliente:dashboard")
    except Exception:
        pass

    tenant = get_current_tenant(request)

    # CORREÇÃO: Superusuários podem acessar sem tenant selecionado
    if not tenant and not request.user.is_superuser:
        messages.error(request, "Por favor, selecione uma empresa para acessar o dashboard.")
        return redirect("core:tenant_select")

    # Para superusuários sem tenant, mostrar dashboard geral
    if request.user.is_superuser and not tenant:
        context = {
            "page_title": "Dashboard do Sistema - Superusuário",
            "page_subtitle": "Visão geral global do sistema",
            "tenant": None,
            "is_superuser_view": True,
            "breadcrumbs_list": [{"title": "Dashboard", "url": None}],
        }
    else:
        # Para usuários normais ou superusuários com tenant selecionado
        tenant_name = tenant.razao_social if tenant and tenant.razao_social else (tenant.name if tenant else "Sistema")
        context = {
            "page_title": f"Dashboard - {tenant_name}",
            "page_subtitle": "Visão geral da empresa" if tenant else "Painel administrativo",
            "tenant": tenant,
            "breadcrumbs_list": [{"title": "Dashboard", "url": None}],
        }

    return render(request, "dashboard.html", context)


def login_view(request):
    """View para autenticação de usuários"""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        # ------------------------------------------------------------------
        # RATE LIMIT GLOBAL POR IP (simples, baseado em cache) - usado pelos testes
        # Configurações dinâmicas (tests sobrescrevem via settings fixture):
        #   LOGIN_GLOBAL_RATE_LIMIT_ATTEMPTS
        #   LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS
        # Incrementa apenas em falhas; ao exceder limite exibe mensagem específica.
        # ------------------------------------------------------------------
        ip = get_client_ip(request)
        limit = getattr(settings, "LOGIN_GLOBAL_RATE_LIMIT_ATTEMPTS", 20)
        window = getattr(settings, "LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS", 300)
        cache_key = f"login_global_rate:{ip}"
        current_attempts = cache.get(cache_key, 0)

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(username=form.cleaned_data.get("username"), password=form.cleaned_data.get("password"))
            if user is not None:
                login(request, user)
                # Reset contador em sucesso
                with contextlib.suppress(Exception):
                    cache.delete(cache_key)

                # CORREÇÃO: Superusuários têm acesso direto ao dashboard
                if user.is_superuser:
                    return redirect("dashboard")

                # NOVO: Fallback para usuários que têm apenas conta de Portal Cliente (sem vínculo TenantUser)
                try:
                    from portal_cliente.models import ContaCliente

                    contas_portal = ContaCliente.objects.filter(usuario=user, ativo=True).select_related(
                        "cliente__tenant"
                    )
                    if contas_portal.exists():
                        # Se não possui nenhum tenant ativo via TenantUser mas tem conta portal, permitir login direto no portal
                        has_tenant_membership = Tenant.objects.filter(tenant_users__user=user, status="active").exists()
                        if not has_tenant_membership:
                            # Se todas as contas portal referem ao mesmo tenant, salvar na sessão (opcional para métricas)
                            tenant_ids = list(
                                {c.cliente.tenant_id for c in contas_portal if c.cliente and c.cliente.tenant_id}
                            )
                            if len(tenant_ids) == 1:
                                request.session["tenant_id"] = tenant_ids[0]
                            return redirect("portal_cliente:dashboard")
                except Exception:
                    # Silenciosamente ignora problemas do módulo do portal para não quebrar login geral
                    pass

                # Verificar tenants do usuário
                user_tenants = Tenant.objects.filter(tenant_users__user=user, status="active")

                if user_tenants.count() == 1:
                    # Se o usuário tem apenas um tenant, redirecionar diretamente
                    tenant = user_tenants.first()
                    request.session["tenant_id"] = tenant.id
                    return redirect("dashboard")
                elif user_tenants.count() > 1:
                    # Se tem múltiplos tenants, ir para seleção
                    return redirect("core:tenant_select")
                else:
                    # Usuário sem tenants ou apenas tenants inativos
                    logout(request)
                    messages.error(request, "Usuário não possui acesso a nenhuma empresa ativa.")
                    return redirect("core:login")
            else:
                messages.error(request, "Credenciais inválidas.")
                # Falha de autenticação explícita (authenticate None) -> incrementar
                try:
                    current_attempts += 1
                    cache.set(cache_key, current_attempts, timeout=window)
                    if current_attempts > limit:
                        # Mensagem esperada pelos testes: começa com "Muitas tentativas de login deste IP"
                        messages.error(
                            request, "Muitas tentativas de login deste IP. Aguarde alguns segundos e tente novamente."
                        )
                except Exception:
                    pass
        else:
            messages.error(request, "Por favor, corrija os erros abaixo.")
            # Form inválido (ex: credenciais erradas). Também contar tentativa.
            try:
                current_attempts += 1
                cache.set(cache_key, current_attempts, timeout=window)
                if current_attempts > limit:
                    messages.error(
                        request, "Muitas tentativas de login deste IP. Aguarde alguns segundos e tente novamente."
                    )
            except Exception:
                pass
    else:
        form = AuthenticationForm()

    return render(request, "core/login.html", {"form": form})


@login_required
def tenant_select(request):
    """View para seleção de tenant quando usuário tem múltiplos acessos"""

    # Verificar se é uma seleção via GET (clique no card)
    if request.method == "GET" and request.GET.get("tenant_id"):
        tenant_id = request.GET.get("tenant_id")

        # CORREÇÃO: Superusuários podem selecionar qualquer tenant
        if request.user.is_superuser:
            try:
                tenant = Tenant.objects.select_related("pessoajuridica_info", "pessoafisica_info").get(
                    id=tenant_id, status="active"
                )
                request.session["tenant_id"] = tenant_id
                return redirect("dashboard")
            except Tenant.DoesNotExist:
                messages.error(request, "Empresa selecionada não encontrada.")
        else:
            # Usuários normais só podem selecionar tenants que têm acesso
            user_tenants = Tenant.objects.filter(tenant_users__user=request.user, status="active").select_related(
                "pessoajuridica_info", "pessoafisica_info"
            )
            if user_tenants.filter(id=tenant_id).exists():
                request.session["tenant_id"] = tenant_id
                return redirect("dashboard")
            else:
                messages.error(request, "Você não tem acesso a essa empresa.")

    # CORREÇÃO: Superusuários podem pular a seleção de tenant
    if request.user.is_superuser:
        # Se é superusuário e chegou aqui, permitir continuar sem tenant
        if request.method == "POST":
            tenant_id = request.POST.get("tenant_id")
            if tenant_id:
                # Se escolheu um tenant, aplicar na sessão
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                    request.session["tenant_id"] = tenant_id
                except Tenant.DoesNotExist:
                    pass
            # Se não escolheu ou escolheu inválido, continuar sem tenant
            return redirect("core:core_home")

        # Para GET, mostrar todos os tenants para o superusuário
        all_tenants = Tenant.objects.filter(status="active").select_related("pessoajuridica_info", "pessoafisica_info")
        context = {
            "user_tenants": all_tenants,  # Corrigido: mudado de 'tenants' para 'user_tenants'
            "page_title": "Seleção de Empresa (Opcional para Superusuário)",
            "is_superuser": True,
        }
        return render(request, "core/tenant_select.html", context)

    # Lógica original para usuários normais
    user_tenants = Tenant.objects.filter(tenant_users__user=request.user, status="active").select_related(
        "pessoajuridica_info", "pessoafisica_info"
    )

    if user_tenants.count() == 0:
        logout(request)
        messages.error(request, "Usuário não possui acesso a nenhuma empresa ativa.")
        return redirect("core:login")
    elif user_tenants.count() == 1:
        # Se tem apenas um, selecionar automaticamente
        tenant = user_tenants.first()
        request.session["tenant_id"] = tenant.id
        return redirect("dashboard")

    if request.method == "POST":
        tenant_id = request.POST.get("tenant_id")
        if tenant_id and user_tenants.filter(id=tenant_id).exists():
            request.session["tenant_id"] = tenant_id
            return redirect("dashboard")
        else:
            messages.error(request, "Empresa selecionada inválida.")

    context = {
        "user_tenants": user_tenants,  # Corrigido: mudado de 'tenants' para 'user_tenants'
        "page_title": "Seleção de Empresa",
    }
    return render(request, "core/tenant_select.html", context)


def logout_view(request):
    """View para logout"""
    logout(request)
    messages.success(request, "Logout realizado com sucesso.")
    return redirect("core:login")


@login_required
def ui_permissions_json(request):
    """Endpoint JSON para consultar permissões de UI.

    Query params suportados:
        - module_key: ex. 'FORNECEDOR' (prioritário)
        - app_label + model_name: ex. 'fornecedores' + 'fornecedor'
        - resource: opcional para granularidade do PermissionResolver
    """
    module_key = request.GET.get("module_key")
    app_label = request.GET.get("app_label")
    model_name = request.GET.get("model_name")
    resource = request.GET.get("resource")
    tenant = get_current_tenant(request)
    ui = build_ui_permissions(
        request.user,
        tenant,
        module_key=module_key,
        app_label=app_label,
        model_name=model_name,
        resource=resource,
    )
    return JsonResponse(ui)


# ============================================================================
# GERENCIAMENTO DE TENANTS - VIEWS CORRIGIDAS E COMENTADAS
# ============================================================================


class TenantListView(UIPermissionsMixin, LoginRequiredMixin, SuperuserRequiredMixin, PageTitleMixin, ListView):
    model = Tenant
    template_name = "core/tenant_list.html"
    page_title = "Gerenciamento de Empresas"
    context_object_name = "object_list"
    paginate_by = 20
    app_label = "core"
    model_name = "tenant"

    def get_queryset(self):
        queryset = Tenant.objects.all().order_by("-created_at")

        # Filtros
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(razao_social__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cpf__icontains=search)
            )

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        tipo_pessoa = self.request.GET.get("tipo_pessoa")
        if tipo_pessoa:
            queryset = queryset.filter(tipo_pessoa=tipo_pessoa)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context.update(
            {
                "add_url": reverse("core:tenant_create"),
                "search_query": self.request.GET.get("search", ""),
                "statistics": [
                    {
                        "value": queryset.count(),
                        "label": _("Total de Empresas"),
                        "icon": "fas fa-building",
                        "bg": "bg-gradient-primary",
                        "text_color": "text-primary",
                        "url": reverse("core:tenant_list"),
                    },
                    {
                        "value": queryset.filter(status="active").count(),
                        "label": _("Ativas"),
                        "icon": "fas fa-check-circle",
                        "bg": "bg-gradient-success",
                        "text_color": "text-success",
                        "url": f"{reverse('core:tenant_list')}?status=active",
                    },
                    {
                        "value": queryset.filter(status="inactive").count(),
                        "label": _("Inativas"),
                        "icon": "fas fa-times-circle",
                        "bg": "bg-gradient-secondary",
                        "text_color": "text-secondary",
                        "url": f"{reverse('core:tenant_list')}?status=inactive",
                    },
                    {
                        "value": queryset.filter(status="suspended").count(),
                        "label": _("Suspensas"),
                        "icon": "fas fa-clock",
                        "bg": "bg-gradient-warning",
                        "text_color": "text-warning",
                        "url": f"{reverse('core:tenant_list')}?status=suspended",
                    },
                ],
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        if "change_status" in request.GET and "new_status" in request.GET:
            tenant_id = request.GET.get("change_status")
            new_status = request.GET.get("new_status")

            status_mapping = {"ativo": "active", "inativo": "inactive", "pendente": "suspended"}

            if new_status in status_mapping:
                try:
                    tenant = get_object_or_404(Tenant, id=tenant_id)
                    tenant.status = status_mapping[new_status]
                    tenant.save()
                    status_display = {"active": "Ativo", "inactive": "Inativo", "suspended": "Pendente"}
                    messages.success(
                        request,
                        f'Status da empresa "{tenant.name}" alterado para "{status_display[tenant.status]}" com sucesso!',
                    )
                except Tenant.DoesNotExist:
                    messages.error(request, "Empresa não encontrada.")
                except Exception as e:
                    messages.error(request, f"Erro ao alterar status: {str(e)}")

            return redirect("core:tenant_list")

        return super().get(request, *args, **kwargs)


"""Views legacy TenantCreateView/TenantUpdateView removidas. Uso exclusivo do wizard."""


class TenantDetailView(UIPermissionsMixin, LoginRequiredMixin, SuperuserRequiredMixin, DetailView):
    model = Tenant
    template_name = "core/tenant_detail.html"
    context_object_name = "tenant"
    app_label = "core"
    model_name = "tenant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Detalhes da Empresa: {self.object.name}"
        context["endereco_principal"] = Endereco.objects.filter(tenant=self.object, tipo="PRINCIPAL").first()
        context["enderecos_adicionais"] = self.object.enderecos_adicionais.all()
        context["contatos"] = self.object.contatos.all()
        context["documentos"] = self.object.documentos.all()
        context["usuarios"] = self.object.tenant_users.select_related("user", "role", "department").all()
        return context


class TenantDeleteView(UIPermissionsMixin, LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = Tenant
    template_name = "core/tenant_confirm_delete.html"
    success_url = reverse_lazy("core:tenant_list")
    app_label = "core"
    model_name = "tenant"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(request, f"Empresa '{self.object.name}' excluída com sucesso.")
        self.object.delete()
        return redirect(success_url)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def tenant_module_config(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == "POST":
        form = ModuleConfigurationForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, f"Configuração de módulos atualizada para '{tenant.name}'.")
            return redirect("core:tenant_detail", pk=tenant.pk)
        else:
            messages.error(request, _("Por favor, corrija os erros no formulário."))
    else:
        initial_modules = []
        if isinstance(tenant.enabled_modules, str):
            try:
                initial_modules = json.loads(tenant.enabled_modules)
            except json.JSONDecodeError:
                initial_modules = []
        elif isinstance(tenant.enabled_modules, dict):
            initial_modules = tenant.enabled_modules.get("modules", [])

        form = ModuleConfigurationForm(initial={"enabled_modules": initial_modules}, tenant=tenant)

    context = {"page_title": f"Configurar Módulos - {tenant.name}", "tenant": tenant, "form": form}
    return render(request, "core/tenant_module_config.html", context)


class CustomUserListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    model = CustomUser
    template_name = "core/user_list.html"
    context_object_name = "users"
    paginate_by = 20


class CustomUserCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserForm
    template_name = "core/user_form.html"
    success_url = reverse_lazy("core:user_list")


class CustomUserUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserForm
    template_name = "core/user_form.html"
    success_url = reverse_lazy("core:user_list")


class CustomUserDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = CustomUser
    template_name = "core/user_confirm_delete.html"
    success_url = reverse_lazy("core:user_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(
            request, f"Usuário '{self.object.get_full_name() or self.object.username}' excluído com sucesso."
        )
        self.object.delete()
        return redirect(success_url)


class RoleListView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, ListView):
    model = Role
    template_name = "core/role_list.html"
    context_object_name = "objects"
    # paginate_by = 10  # Removido para manter consistência com outros templates
    app_label = "core"
    model_name = "role"

    def get_queryset(self):
        # Para superusuários, mostrar todos os cargos se não há tenant específico
        if self.request.user.is_superuser:
            # Se não há tenant selecionado, mostrar cargos de todos os tenants
            if not hasattr(self.request, "tenant") or not self.request.tenant:
                queryset = Role.objects.all()
            else:
                queryset = Role.objects.filter(tenant=self.request.tenant)
        else:
            # Para usuários normais, apenas do tenant associado
            queryset = Role.objects.filter(tenant=self.request.tenant)

        # Filtros de busca
        name = self.request.GET.get("name")
        description = self.request.GET.get("description")
        has_users = self.request.GET.get("has_users")

        if name:
            queryset = queryset.filter(name__icontains=name)

        if description:
            queryset = queryset.filter(description__icontains=description)

        if has_users == "true":
            queryset = queryset.filter(tenantuser__isnull=False).distinct()
        elif has_users == "false":
            queryset = queryset.filter(tenantuser__isnull=True)

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Manter 'roles' como alias para compatibilidade
        context["roles"] = context.get("objects", [])

        # Informação sobre o tenant atual para superusuários
        if self.request.user.is_superuser:
            if not hasattr(self.request, "tenant") or not self.request.tenant:
                context["current_tenant"] = None  # Mostrando todos os tenants
                context["showing_all_tenants"] = True
            else:
                context["current_tenant"] = self.request.tenant
                context["showing_all_tenants"] = False

        # Estatísticas para os cards
        if self.request.user.is_superuser:
            if not hasattr(self.request, "tenant") or not self.request.tenant:
                all_roles = Role.objects.all()
            else:
                all_roles = Role.objects.filter(tenant=self.request.tenant)
        else:
            all_roles = Role.objects.filter(tenant=self.request.tenant)

        total_roles = all_roles.count()
        roles_with_users = all_roles.filter(tenantuser__isnull=False).distinct().count()
        roles_without_users = total_roles - roles_with_users
        active_roles = all_roles.filter(is_active=True).count() if hasattr(Role, "is_active") else total_roles

        context["statistics"] = [
            {
                "label": "Total de Cargos",
                "value": total_roles,
                "icon": "fas fa-user-tag",
                "color": "primary",
                "subtitle": f"{roles_with_users} em uso",
            },
            {
                "label": "Cargos em Uso",
                "value": roles_with_users,
                "icon": "fas fa-users",
                "color": "success",
                "subtitle": f"{(roles_with_users / total_roles * 100):.1f}% do total"
                if total_roles > 0
                else "0% do total",
            },
            {
                "label": "Cargos Vagos",
                "value": roles_without_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": f"{(roles_without_users / total_roles * 100):.1f}% do total"
                if total_roles > 0
                else "0% do total",
            },
            {
                "label": "Cargos Ativos",
                "value": active_roles,
                "icon": "fas fa-check-circle",
                "color": "info",
                "subtitle": f"{(active_roles / total_roles * 100):.1f}% do total" if total_roles > 0 else "0% do total",
            },
        ]

        return context


class RoleCreateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = "core/role_form.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        # Passar tenant atual para filtrar departamentos quando não superuser
        if not self.request.user.is_superuser:
            kwargs["tenant"] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        # Se usuário não é superuser, força tenant atual
        if not self.request.user.is_superuser:
            form.instance.tenant = self.request.tenant
        # Superuser: se deixou em branco permanece global (tenant=None)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Recent roles for sidebar
        if self.request.user.is_superuser:
            context["recent_roles"] = Role.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_roles"] = Role.objects.filter(tenant=self.request.tenant).order_by("-created_at")[:3]
        return context


class RoleDeleteView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DeleteView):
    model = Role
    template_name = "core/role_confirm_delete.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_queryset(self):
        return Role.objects.filter(tenant=self.request.tenant)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(request, f"Papel '{self.object.name}' excluído com sucesso.")
        self.object.delete()
        return redirect(success_url)


class RoleDetailView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DetailView):
    """View para visualizar detalhes de um cargo"""

    model = Role
    template_name = "core/role_detail.html"
    context_object_name = "role"
    app_label = "core"
    model_name = "role"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(tenant=self.request.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()

        # Usuários associados ao cargo
        context["tenant_users"] = TenantUser.objects.filter(role=role).select_related("user", "department")

        # Permissões do cargo
        context["permissions"] = role.permissions.all().order_by("content_type__app_label", "codename")

        return context


@login_required
@require_http_methods(["GET", "POST"])
def role_permissions(request, pk):
    """View para gerenciar permissões de um cargo"""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    # Verificar permissões
    if not request.user.is_superuser:
        tenant = get_current_tenant(request)
        if not tenant:
            messages.error(request, "Selecione uma empresa primeiro.")
            return redirect("core:tenant_select")

        # Verificar se é admin do tenant
        if not TenantUser.objects.filter(tenant=tenant, user=request.user, is_tenant_admin=True).exists():
            messages.error(request, "Você não tem permissão para gerenciar permissões.")
            return redirect("core:role_list")

    # Buscar o cargo
    try:
        if request.user.is_superuser:
            role = Role.objects.get(pk=pk)
        else:
            role = Role.objects.get(pk=pk, tenant=get_current_tenant(request))
    except Role.DoesNotExist:
        messages.error(request, "Cargo não encontrado.")
        return redirect("core:role_list")

    if request.method == "POST":
        # Atualizar permissões
        permission_ids = request.POST.getlist("permissions")

        # Converter para inteiros
        try:
            permission_ids = [int(pid) for pid in permission_ids]
        except ValueError:
            messages.error(request, "IDs de permissão inválidos.")
            return redirect("core:role_permissions", pk=pk)

        # Atualizar permissões
        permissions = Permission.objects.filter(id__in=permission_ids)
        role.permissions.set(permissions)

        messages.success(request, f"Permissões do cargo '{role.name}' atualizadas com sucesso.")
        return redirect("core:role_detail", pk=pk)

    # GET - Exibir formulário
    # Buscar todas as permissões organizadas por app
    content_types = ContentType.objects.all().order_by("app_label", "model")
    permissions_by_app = {}

    for ct in content_types:
        app_label = ct.app_label
        if app_label not in permissions_by_app:
            permissions_by_app[app_label] = {}

        permissions = Permission.objects.filter(content_type=ct).order_by("codename")
        if permissions.exists():
            permissions_by_app[app_label][ct.model] = permissions

    # Remover apps vazios
    permissions_by_app = {k: v for k, v in permissions_by_app.items() if v}

    context = {
        "role": role,
        "permissions_by_app": permissions_by_app,
        "current_permissions": list(role.permissions.values_list("id", flat=True)),
    }

    return render(request, "core/role_permissions.html", context)


@login_required
def switch_tenant(request, tenant_id):
    """
    View para trocar de tenant (empresa).
    Permite que usuários alternem entre diferentes empresas.
    """
    try:
        # Verificar se o tenant existe
        tenant = get_object_or_404(Tenant, id=tenant_id)

        # Para superusuários, permitir acesso a qualquer tenant
        if request.user.is_superuser:
            # Definir o tenant na sessão
            request.session["tenant_id"] = tenant_id
            request.session.modified = True
            with contextlib.suppress(Exception):
                request.session.save()
            messages.success(request, f"Empresa alterada para: {tenant.name}")

            # Redirecionar para o dashboard ou página anterior
            next_url = request.GET.get("next", reverse("dashboard"))
            return redirect(next_url)

        # Para usuários comuns, verificar se têm acesso ao tenant
        try:
            TenantUser.objects.get(user=request.user, tenant=tenant)

            # Verificar se o usuário está ativo no tenant
            if not request.user.is_active:
                messages.error(request, "Sua conta está inativa.")
                return redirect("core:tenant_select")

            # Definir o tenant na sessão
            request.session["tenant_id"] = tenant_id
            request.session.modified = True
            with contextlib.suppress(Exception):
                request.session.save()
            messages.success(request, f"Empresa alterada para: {tenant.name}")

            # Redirecionar para o dashboard ou página anterior
            next_url = request.GET.get("next", reverse("dashboard"))
            return redirect(next_url)

        except TenantUser.DoesNotExist:
            messages.error(request, "Você não tem acesso a esta empresa.")
            return redirect("core:tenant_select")

    except Tenant.DoesNotExist:
        messages.error(request, "Empresa não encontrada.")
        return redirect("core:tenant_select")

    except Exception as e:
        messages.error(request, f"Erro ao trocar de empresa: {str(e)}")
        return redirect("core:tenant_select")


# ============================================================================
# VIEWS DE GERENCIAMENTO DE USUÁRIOS DO TENANT (TenantUser)
# ============================================================================


class TenantUserListView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, ListView):
    model = TenantUser
    template_name = "core/tenant_user_list.html"
    context_object_name = "objects"
    paginate_by = 25
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = TenantUser.objects.all().select_related("user", "role", "department")
        else:
            queryset = TenantUser.objects.filter(tenant=self.request.tenant).select_related(
                "user", "role", "department"
            )

        # Filtros de busca
        nome = self.request.GET.get("nome")
        if nome:
            queryset = queryset.filter(
                models.Q(user__first_name__icontains=nome)
                | models.Q(user__last_name__icontains=nome)
                | models.Q(user__username__icontains=nome)
            )

        email = self.request.GET.get("email")
        if email:
            queryset = queryset.filter(user__email__icontains=email)

        is_admin = self.request.GET.get("is_admin")
        if is_admin == "true":
            queryset = queryset.filter(is_tenant_admin=True)
        elif is_admin == "false":
            queryset = queryset.filter(is_tenant_admin=False)

        status = self.request.GET.get("status")
        if status == "ativo":
            queryset = queryset.filter(user__is_active=True)
        elif status == "inativo":
            queryset = queryset.filter(user__is_active=False)

        return queryset.order_by("user__first_name", "user__username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Manter 'tenant_users' como alias para compatibilidade
        context["tenant_users"] = context.get("objects", [])

        # Estatísticas para os cards
        if self.request.user.is_superuser:
            all_users = TenantUser.objects.all()
        else:
            all_users = TenantUser.objects.filter(tenant=self.request.tenant)

        total_users = all_users.count()
        active_users = all_users.filter(user__is_active=True).count()
        inactive_users = all_users.filter(user__is_active=False).count()
        admin_users = all_users.filter(is_tenant_admin=True).count()

        context["statistics"] = [
            {
                "label": "Total de Usuários",
                "value": total_users,
                "icon": "fas fa-users",
                "color": "primary",
                "subtitle": f"{active_users} ativos",
            },
            {
                "label": "Usuários Ativos",
                "value": active_users,
                "icon": "fas fa-user-check",
                "color": "success",
                "subtitle": f"{(active_users / total_users * 100):.1f}% do total" if total_users > 0 else "0% do total",
            },
            {
                "label": "Usuários Inativos",
                "value": inactive_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": f"{(inactive_users / total_users * 100):.1f}% do total"
                if total_users > 0
                else "0% do total",
            },
            {
                "label": "Administradores",
                "value": admin_users,
                "icon": "fas fa-user-shield",
                "color": "warning",
                "subtitle": f"{(admin_users / total_users * 100):.1f}% do total" if total_users > 0 else "0% do total",
            },
        ]

        return context


class TenantUserCreateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, CreateView):
    model = TenantUser
    form_class = TenantUserForm
    template_name = "core/tenant_user_form.html"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        if not self.request.user.is_superuser:
            kwargs["tenant"] = self.request.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Adicionar últimas vinculações
        if self.request.user.is_superuser:
            recent_tenant_users = TenantUser.objects.select_related("user", "tenant", "role", "department").order_by(
                "-created_at"
            )[:5]
        else:
            recent_tenant_users = (
                TenantUser.objects.filter(tenant=self.request.tenant)
                .select_related("user", "role", "department")
                .order_by("-created_at")[:5]
            )

        context["recent_tenant_users"] = recent_tenant_users
        return context

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)


class TenantUserUpdateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, UpdateView):
    model = TenantUser
    form_class = TenantUserForm
    template_name = "core/tenant_user_form.html"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TenantUser.objects.all()
        return TenantUser.objects.filter(tenant=self.request.tenant)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not self.request.user.is_superuser:
            kwargs["tenant"] = self.request.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Adicionar últimas vinculações
        if self.request.user.is_superuser:
            recent_tenant_users = TenantUser.objects.select_related("user", "tenant", "role", "department").order_by(
                "-created_at"
            )[:5]
        else:
            recent_tenant_users = (
                TenantUser.objects.filter(tenant=self.request.tenant)
                .select_related("user", "role", "department")
                .order_by("-created_at")[:5]
            )

        context["recent_tenant_users"] = recent_tenant_users
        return context

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)


class TenantUserDeleteView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DeleteView):
    model = TenantUser
    template_name = "core/tenant_user_confirm_delete.html"
    context_object_name = "tenant_user"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self):
        return TenantUser.objects.filter(tenant=self.request.tenant).select_related("user", "role", "department")


@login_required
def tenant_user_permissions(request, pk):
    """View para gerenciar permissões específicas do usuário"""
    # Super admin pode acessar qualquer TenantUser, admin comum só do seu tenant e sendo admin
    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=request.tenant)
        from django.http import HttpResponseForbidden

        if not TenantUser.objects.filter(tenant=request.tenant, user=request.user, is_tenant_admin=True).exists():
            messages.error(request, "Você não tem permissão para gerenciar permissões neste tenant.")
            return HttpResponseForbidden("Sem permissão")

    # Por enquanto, apenas uma mensagem informativa
    messages.info(
        request,
        f"Gerenciamento de permissões para {tenant_user.user.get_full_name() or tenant_user.user.username} será implementado em breve.",
    )

    return redirect("core:tenant_user_list")


@login_required
def tenant_user_toggle_status(request, pk):
    """Toggle do status ativo/inativo do usuário"""
    # Super admin pode acessar qualquer TenantUser, admin comum só do seu tenant e sendo admin
    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=request.tenant)
        from django.http import HttpResponseForbidden

        if not TenantUser.objects.filter(tenant=request.tenant, user=request.user, is_tenant_admin=True).exists():
            messages.error(request, "Você não tem permissão para alterar status neste tenant.")
            return HttpResponseForbidden("Sem permissão")

    tenant_user.user.is_active = not tenant_user.user.is_active
    tenant_user.user.save()

    status = "ativado" if tenant_user.user.is_active else "desativado"
    messages.success(request, f"Usuário {tenant_user.user.get_full_name() or tenant_user.user.username} foi {status}.")

    return redirect("core:tenant_user_list")


@login_required
def tenant_user_reset_password(request, pk):
    """Reset da senha do usuário"""
    # Super admin pode acessar qualquer TenantUser, admin comum só do seu tenant e sendo admin
    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        # Restringe ao tenant atual
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=request.tenant)
        # Exigir que o solicitante seja admin do tenant
        from django.http import HttpResponseForbidden

        if not TenantUser.objects.filter(tenant=request.tenant, user=request.user, is_tenant_admin=True).exists():
            messages.error(request, "Você não tem permissão para resetar senhas neste tenant.")
            return HttpResponseForbidden("Sem permissão")

    # Implementar lógica de reset de senha
    messages.info(
        request,
        f"Reset de senha para {tenant_user.user.get_full_name() or tenant_user.user.username} será implementado em breve.",
    )

    return redirect("core:tenant_user_list")


class RoleUpdateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = "core/role_form.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(tenant=self.request.tenant)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not self.request.user.is_superuser or self.request.tenant:
            kwargs["tenant"] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Recent roles for sidebar
        if self.request.user.is_superuser:
            context["recent_roles"] = Role.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_roles"] = Role.objects.filter(tenant=self.request.tenant).order_by("-created_at")[:3]
        return context


class TenantUserDetailView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DetailView):
    model = TenantUser
    template_name = "core/tenant_user_detail.html"
    context_object_name = "tenant_user"
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TenantUser.objects.all()
        return TenantUser.objects.filter(tenant=self.request.tenant)


# ============================================================================
# VIEWS DE GERENCIAMENTO DE DEPARTAMENTOS
# ============================================================================


class DepartmentListView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, ListView):
    model = Department
    template_name = "core/department_list.html"
    context_object_name = "object_list"
    # paginate_by = 25  # Removido para manter consistência com outros templates
    app_label = "core"
    model_name = "department"

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = Department.objects.all().select_related("tenant")
        else:
            # Incluir globais + do tenant
            queryset = Department.objects.filter(
                models.Q(tenant=self.request.tenant) | models.Q(tenant__isnull=True)
            ).select_related("tenant")

        # Search functionality
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Status filter (placeholder for future use)
        status = self.request.GET.get("status")
        if status == "active":
            # Add logic for active departments if needed
            pass
        elif status == "inactive":
            # Add logic for inactive departments if needed
            pass

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estatísticas para os cards
        if self.request.user.is_superuser:
            all_departments = Department.objects.all()
        else:
            all_departments = Department.objects.filter(
                models.Q(tenant=self.request.tenant) | models.Q(tenant__isnull=True)
            )

        total_departments = all_departments.count()
        departments_with_users = all_departments.filter(tenantuser__isnull=False).distinct().count()
        departments_without_users = total_departments - departments_with_users
        recent_departments = all_departments.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()

        context["statistics"] = [
            {
                "label": "Total de Departamentos",
                "value": total_departments,
                "icon": "fas fa-sitemap",
                "color": "primary",
                "subtitle": f"{departments_with_users} com usuários",
            },
            {
                "label": "Com Usuários",
                "value": departments_with_users,
                "icon": "fas fa-users",
                "color": "success",
                "subtitle": f"{(departments_with_users / total_departments * 100):.1f}% do total"
                if total_departments > 0
                else "0% do total",
            },
            {
                "label": "Sem Usuários",
                "value": departments_without_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": f"{(departments_without_users / total_departments * 100):.1f}% do total"
                if total_departments > 0
                else "0% do total",
            },
            {
                "label": "Criados Recentemente",
                "value": recent_departments,
                "icon": "fas fa-plus-circle",
                "color": "info",
                "subtitle": "Últimos 30 dias",
            },
        ]

        return context


class DepartmentCreateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "core/department_form.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add recent departments for the "Últimos Cadastros" card
        if self.request.user.is_superuser:
            context["recent_departments"] = Department.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_departments"] = Department.objects.filter(tenant=self.request.tenant).order_by(
                "-created_at"
            )[:3]
        return context

    def form_valid(self, form):
        # Superuser: pode deixar sem tenant (global) ou selecionar um tenant
        if self.request.user.is_superuser:
            chosen_tenant = form.cleaned_data.get("tenant")
            form.instance.tenant = chosen_tenant  # pode ser None (global)
        else:
            if not getattr(self.request, "tenant", None):
                form.add_error(None, "Nenhuma empresa ativa no contexto. Selecione uma antes de criar o departamento.")
                return self.form_invalid(form)
            form.instance.tenant = self.request.tenant
        # Executa validação explicitamente (para acionar clean custom com instância populada)
        form.instance.full_clean()
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Passa request para o form decidir exposição de tenant
        kwargs["request"] = self.request
        return kwargs


class DepartmentUpdateView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "core/department_form.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add recent departments for the "Últimos Cadastros" card
        if self.request.user.is_superuser:
            context["recent_departments"] = Department.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_departments"] = Department.objects.filter(tenant=self.request.tenant).order_by(
                "-created_at"
            )[:3]
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Para edição não permitimos alterar tenant: não passamos request como superuser toggle de campo
        # Mas se desejarmos mostrar (somente leitura) poderíamos implementar field disabled; por ora ocultamos.
        return kwargs

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=self.request.tenant)


class DepartmentDetailView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DetailView):
    model = Department
    template_name = "core/department_detail.html"
    context_object_name = "department"
    app_label = "core"
    model_name = "department"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=self.request.tenant)


class DepartmentDeleteView(UIPermissionsMixin, LoginRequiredMixin, TenantAdminOrSuperuserMixin, DeleteView):
    model = Department
    template_name = "core/department_confirm_delete.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=self.request.tenant)


@login_required
def core_reports(request):
    """View para relatórios do módulo Core"""
    tenant = get_current_tenant(request)

    # Verificação de permissão para relatórios
    if not request.user.is_superuser and not tenant:
        messages.error(request, "Nenhuma empresa selecionada. Por favor, escolha uma para continuar.")
        return redirect("core:tenant_select")

    # Coleta de dados para os relatórios
    if request.user.is_superuser:
        # Superusuário vê dados de todos os tenants
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status="active").count()
        inactive_tenants = Tenant.objects.filter(status="inactive").count()
        total_users = CustomUser.objects.count()
        total_departments = Department.objects.count()
        total_roles = Role.objects.count()

        # Relatórios específicos por tenant
        tenants_data = []
        for t in Tenant.objects.all():
            # Corrigir a consulta de usuários por tenant
            users_count = TenantUser.objects.filter(tenant=t).count()
            tenants_data.append(
                {
                    "tenant": t,
                    "users_count": users_count,
                    "departments_count": t.departments.count(),
                    "roles_count": t.roles.count(),
                }
            )
    else:
        # Usuário normal vê apenas dados do seu tenant
        total_tenants = 1
        active_tenants = 1 if tenant.status == "active" else 0
        inactive_tenants = 1 if tenant.status == "inactive" else 0
        total_users = TenantUser.objects.filter(tenant=tenant).count()
        total_departments = tenant.departments.count()
        total_roles = tenant.roles.count()
        tenants_data = [
            {
                "tenant": tenant,
                "users_count": total_users,
                "departments_count": total_departments,
                "roles_count": total_roles,
            }
        ]

    context = {
        "page_title": "Relatórios - Módulo Core",
        "current_tenant": tenant,
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "inactive_tenants": inactive_tenants,
        "total_users": total_users,
        "total_departments": total_departments,
        "total_roles": total_roles,
        "tenants_data": tenants_data,
    }

    return render(request, "core/reports.html", context)


@user_passes_test(lambda u: u.is_superuser)
def system_global_configurations(request):
    """
    Configurações GLOBAIS do Sistema (apenas Super Admin)
    - Parâmetros do sistema completo
    - Configurações de segurança global
    - Backup e restore
    - Monitoramento de performance global
    """
    context = {
        "page_title": "Configurações Globais do Sistema",
        "page_subtitle": "Parâmetros e configurações globais da plataforma Pandora ERP",
        "page_icon": "fas fa-globe",
        # Configurações do sistema
        "system_configs": {
            "maintenance_mode": getattr(settings, "MAINTENANCE_MODE", False),
            "debug_mode": getattr(settings, "DEBUG", False),
            "allowed_hosts": getattr(settings, "ALLOWED_HOSTS", []),
            "database_engine": settings.DATABASES["default"]["ENGINE"],
            "email_backend": getattr(settings, "EMAIL_BACKEND", ""),
            "default_from_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            "time_zone": getattr(settings, "TIME_ZONE", "UTC"),
            "language_code": getattr(settings, "LANGUAGE_CODE", "pt-br"),
        },
        # Métricas globais
        "global_metrics": {
            "total_tenants": Tenant.objects.count(),
            "active_tenants": Tenant.objects.filter(status="ativo").count(),
            "total_users": CustomUser.objects.count(),
            "total_superusers": CustomUser.objects.filter(is_superuser=True).count(),
        },
    }

    return render(request, "core/global_configurations.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def tenant_documents(request, pk):
    """Página completa de Documentos do Tenant (versionados por tipo).
    - Lista os tipos aplicáveis ao alvo EMPRESA a partir dos Itens Auxiliares nas categorias de documentos
    - Exibe para cada tipo o status e a versão atual
    - Mostra histórico de versões (últimas 5 por tipo)
    - Permite criar uma nova versão via formulário (upload + metadados)
    """
    tenant = get_object_or_404(Tenant, pk=pk)

    # Filtrar tipos de documentos aplicáveis a EMPRESA
    tipos_qs = ItemAuxiliar.objects.filter(ativo=True)
    tipos_qs = tipos_qs.filter(models.Q(alvo="empresa") | models.Q(targets__code="empresa")).distinct()
    tipos_qs = tipos_qs.filter(
        categoria__slug__in=["documentos-da-empresa", "documentos-financeiros", "outros-documentos"]
    )
    tipos_qs = tipos_qs.select_related("categoria").order_by("categoria__ordem", "ordem", "nome")

    # Mapear por categoria
    categorias = {}
    for tipo in tipos_qs:
        cat = tipo.categoria
        categorias.setdefault(cat.slug, {"categoria": cat, "tipos": []})
        categorias[cat.slug]["tipos"].append(tipo)

    # Buscar cabeçalhos existentes para o tenant
    docs = {
        (d.tipo_id): d
        for d in EmpresaDocumento.objects.filter(tenant=tenant, tipo__in=tipos_qs).select_related("tipo").all()
    }

    if request.method == "POST":
        form = EmpresaDocumentoVersaoCreateForm(request.POST, request.FILES, tenant=tenant)
        if form.is_valid():
            versao = form.save(user=request.user)
            messages.success(
                request, _(f"Nova versão criada com sucesso: {versao.documento.tipo.nome} v{versao.versao}")
            )
            return redirect("core:tenant_documents", pk=tenant.pk)
        else:
            messages.error(request, _("Corrija os erros no formulário de nova versão."))
    else:
        form = EmpresaDocumentoVersaoCreateForm(tenant=tenant)

    # Montar visão por categoria com histórico recente
    categorias_view = []
    for _slug, bucket in categorias.items():
        cat = bucket["categoria"]
        tipos = bucket["tipos"]
        tipos_data = []
        for tipo in tipos:
            cab = docs.get(tipo.id)
            historico = []
            if cab:
                historico = list(EmpresaDocumentoVersao.objects.filter(documento=cab).order_by("-versao")[:5])
            tipos_data.append(
                {
                    "tipo": tipo,
                    "cabecalho": cab,
                    "historico": historico,
                }
            )
        categorias_view.append(
            {
                "categoria": cat,
                "tipos_data": tipos_data,
            }
        )

    context = {
        "page_title": _("Documentos da Empresa"),
        "tenant": tenant,
        "categorias_view": categorias_view,
        "form_nova_versao": form,
    }
    return render(request, "core/tenant_documents.html", context)

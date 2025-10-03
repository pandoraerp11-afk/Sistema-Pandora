"""Módulo de views do core do sistema Pandora.

Este módulo contém as views principais e de gerenciamento do sistema,
incluindo autenticação, dashboards, gerenciamento de tenants, usuários,
cargos e configurações.
"""

# core/views.py
import contextlib
import json
import logging
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView

from cadastros_gerais.models import ItemAuxiliar
from core.utils import get_client_ip, get_current_tenant
from portal_cliente.models import ContaCliente
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
from .home_system import CoreHomeSystem
from .mixins import (
    PageTitleMixin,
    SuperuserRequiredMixin,
    TenantAdminOrSuperuserMixin,
)
from .models import (
    CustomUser,
    Department,
    EmpresaDocumento,
    Endereco,
    Role,
    Tenant,
    TenantUser,
)

logger = logging.getLogger(__name__)


# ============================================================================
# DASHBOARD E VIEWS GLOBAIS
# ============================================================================


@login_required
def core_home(request: HttpRequest) -> HttpResponse:
    """Dashboard do módulo CORE.

    Exibe métricas e informações sobre empresas, usuários e configurações do sistema.
    Acessível apenas por superusuários, exibe métricas globais do sistema.
    """
    if not isinstance(request.user, CustomUser) or not request.user.is_superuser:
        messages.error(
            request,
            "Acesso negado. Apenas superusuários podem acessar este dashboard.",
        )
        return redirect("core:login")

    try:
        home_system = CoreHomeSystem(user=request.user)
        context = home_system.get_home_context()
        context.update(
            {
                "page_title": "Home do Módulo CORE",
                "breadcrumbs_list": [
                    {"title": "Core", "url": None},
                    {"title": "Home", "url": None},
                ],
            },
        )
        return render(request, "core/core_home.html", context)
    except Exception as e:
        logger.exception("Erro ao carregar dados do dashboard do core.")
        messages.warning(request, f"Erro ao carregar dados do dashboard: {e!s}")
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
            "breadcrumbs_list": [
                {"title": "Core", "url": None},
                {"title": "Dashboard", "url": None},
            ],
        }
        return render(request, "core/core_home.html", context)


@login_required
def core_reports(request: HttpRequest) -> HttpResponse:
    """Página de relatórios do módulo CORE.

    Mantém o comportamento alinhado ao dashboard do CORE: acesso para superusuários.
    """
    if not isinstance(request.user, CustomUser) or not request.user.is_superuser:
        messages.error(request, "Acesso negado. Apenas superusuários podem acessar Relatórios do Core.")
        return redirect("core:login")

    tenant = get_current_tenant(request)
    context = {
        "page_title": "Relatórios do Módulo CORE",
        "tenant": tenant,
        "breadcrumbs_list": [
            {"title": "Core", "url": reverse("core:core_home")},
            {"title": "Relatórios", "url": None},
        ],
    }
    return render(request, "core/reports.html", context)


@user_passes_test(lambda u: u.is_superuser)
def system_global_configurations(request: HttpRequest) -> HttpResponse:
    """Configurações Globais do Sistema (somente Super Admin).

    Implementação restaurada baseada no backup: exibe parâmetros globais,
    métricas agregadas e informações de ambiente.
    """
    context = {
        "page_title": "Configurações Globais do Sistema",
        "page_subtitle": "Parâmetros e configurações globais da plataforma Pandora ERP",
        "page_icon": "fas fa-globe",
        "system_configs": {
            "maintenance_mode": getattr(settings, "MAINTENANCE_MODE", False),
            "debug_mode": getattr(settings, "DEBUG", False),
            "allowed_hosts": getattr(settings, "ALLOWED_HOSTS", []),
            "database_engine": settings.DATABASES.get("default", {}).get("ENGINE", ""),
            "email_backend": getattr(settings, "EMAIL_BACKEND", ""),
            "default_from_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            "time_zone": getattr(settings, "TIME_ZONE", "UTC"),
            "language_code": getattr(settings, "LANGUAGE_CODE", "pt-br"),
        },
        "global_metrics": {
            "total_tenants": Tenant.objects.count(),
            "active_tenants": Tenant.objects.filter(status="ativo").count(),
            "total_users": CustomUser.objects.count(),
            "total_superusers": CustomUser.objects.filter(is_superuser=True).count(),
        },
    }

    return render(request, "core/global_configurations.html", context)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard principal do sistema (não específico do módulo CORE).

    Exibe visão geral da empresa selecionada com métricas de todos os módulos.
    """
    try:
        has_tenant_membership = Tenant.objects.filter(
            tenant_users__user=request.user,
            status="active",
        ).exists()
        if not has_tenant_membership and ContaCliente.objects.filter(usuario=request.user, ativo=True).exists():
            return redirect("portal_cliente:dashboard")
    except ImportError:
        logger.warning("Módulo 'portal_cliente' não encontrado. Ignorando verificação.")
    except Exception:
        logger.exception("Erro ao verificar conta do portal do cliente.")

    tenant = get_current_tenant(request)

    if not tenant and not request.user.is_superuser:
        messages.error(
            request,
            "Por favor, selecione uma empresa para acessar o dashboard.",
        )
        return redirect("core:tenant_select")

    if request.user.is_superuser and not tenant:
        context = {
            "page_title": "Dashboard do Sistema - Superusuário",
            "page_subtitle": "Visão geral global do sistema",
            "tenant": None,
            "is_superuser_view": True,
            "breadcrumbs_list": [{"title": "Dashboard", "url": None}],
        }
    else:
        tenant_name = tenant.razao_social if tenant and tenant.razao_social else (tenant.name if tenant else "Sistema")
        context = {
            "page_title": f"Dashboard - {tenant_name}",
            "page_subtitle": "Visão geral da empresa" if tenant else "Painel administrativo",
            "tenant": tenant,
            "breadcrumbs_list": [{"title": "Dashboard", "url": None}],
        }

    return render(request, "dashboard.html", context)


def _is_login_rate_limited(request: HttpRequest) -> bool:
    """Verifica se o IP atingiu o limite de tentativas de login dentro da janela."""
    ip = get_client_ip(request)
    limit = getattr(settings, "LOGIN_GLOBAL_RATE_LIMIT_ATTEMPTS", 20)
    window = getattr(settings, "LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS", 300)
    cache_key = f"login_global_rate:{ip}"

    data = cache.get(cache_key)
    now_ts = timezone.now().timestamp()
    if not isinstance(data, dict) or "count" not in data or "first_ts" not in data:
        data = {"count": 0, "first_ts": now_ts}
    elif now_ts - float(data["first_ts"]) > float(window):
        data = {"count": 0, "first_ts": now_ts}
        cache.set(cache_key, data, timeout=window * 2 if window else None)

    if int(data["count"]) >= int(limit):
        messages.error(
            request,
            "Muitas tentativas de login deste IP. Aguarde alguns segundos e tente novamente.",
        )
        return True
    return False


def _increment_login_attempts(request: HttpRequest) -> None:
    """Incrementa o contador de tentativas de login por IP dentro da janela."""
    ip = get_client_ip(request)
    window = getattr(settings, "LOGIN_GLOBAL_RATE_LIMIT_WINDOW_SECONDS", 300)
    cache_key = f"login_global_rate:{ip}"
    now_ts = timezone.now().timestamp()
    try:
        data = cache.get(cache_key)
        if (
            not isinstance(data, dict)
            or "count" not in data
            or "first_ts" not in data
            or now_ts - float(data["first_ts"]) > float(window)
        ):
            data = {"count": 0, "first_ts": now_ts}
        data["count"] = int(data.get("count", 0)) + 1
        cache.set(cache_key, data, timeout=window * 2 if window else None)
    except Exception:
        logger.exception("Falha ao incrementar o contador de rate limit de login.")


def _clear_rate_limit_messages(request: HttpRequest) -> None:
    """Remove mensagens antigas de rate limit da fila de mensagens."""
    storage = get_messages(request)
    preserved: list[tuple[int, str, str | None]] = []
    for m in storage:
        txt = str(getattr(m, "message", ""))
        if "Muitas tentativas" not in txt:
            preserved.append((m.level, m.message, getattr(m, "extra_tags", None)))
    for level, msg_txt, extra in preserved:
        if extra is not None:
            messages.add_message(request, level, msg_txt, extra_tags=str(extra))
        else:
            messages.add_message(request, level, msg_txt)


def _handle_portal_redirect(
    request: HttpRequest,
    user: CustomUser,
) -> HttpResponse | None:
    """Redireciona para o portal do cliente se o usuário for apenas de portal."""
    try:
        contas_portal = ContaCliente.objects.filter(
            usuario=user,
            ativo=True,
        ).select_related("cliente__tenant")
        if contas_portal.exists():
            has_tenant_membership = Tenant.objects.filter(
                tenant_users__user=user,
                status="active",
            ).exists()
            if not has_tenant_membership:
                tenant_ids = {c.cliente.tenant_id for c in contas_portal if c.cliente and c.cliente.tenant_id}
                if len(tenant_ids) == 1:
                    request.session["tenant_id"] = tenant_ids.pop()
                return redirect("portal_cliente:dashboard")
    except ImportError:
        logger.warning("Módulo 'portal_cliente' não encontrado. Ignorando.")
    except Exception:
        logger.exception("Erro ao processar redirecionamento para o portal do cliente.")
    return None


def _handle_tenant_login_redirect(
    request: HttpRequest,
    user: CustomUser,
) -> HttpResponse:
    """Decide para onde redirecionar o usuário com base em seus tenants."""
    user_tenants = Tenant.objects.filter(tenant_users__user=user, status="active")
    tenant_count = user_tenants.count()

    if tenant_count == 1:
        tenant = user_tenants.first()
        if tenant:
            request.session["tenant_id"] = tenant.id
        return redirect("dashboard")
    if tenant_count > 1:
        return redirect("core:tenant_select")

    logout(request)
    messages.error(request, "Usuário não possui acesso a nenhuma empresa ativa.")
    return redirect("core:login")


def _decide_post_login_redirect(request: HttpRequest, user: CustomUser) -> HttpResponse:
    """Decide o redirecionamento após login para um usuário válido."""
    if user.is_superuser:
        return redirect("dashboard")
    portal_redirect = _handle_portal_redirect(request, user)
    return portal_redirect or _handle_tenant_login_redirect(request, user)


def login_view(request: HttpRequest) -> HttpResponse:
    """Realiza o login do usuário e redireciona para a página apropriada."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    # Checagem de rate limit antes de validar o formulário
    if request.method == "POST":
        if _is_login_rate_limited(request):
            form = AuthenticationForm(request, data=request.POST or None)
            return render(request, "core/login.html", {"form": form, "page_title": "Login"})
        # Janela expirou: garantir que mensagem antiga não persista
        _clear_rate_limit_messages(request)

    form = AuthenticationForm(request, data=request.POST or None)
    if not form.is_valid():
        # Incrementa tentativas somente quando há POST inválido
        if request.method == "POST":
            _increment_login_attempts(request)
        return render(request, "core/login.html", {"form": form, "page_title": "Login"})

    user = form.get_user()
    login(request, user)
    with contextlib.suppress(Exception):
        cache.delete(f"login_global_rate:{get_client_ip(request)}")

    if not isinstance(user, CustomUser):
        # Fallback para usuários que não são CustomUser, se aplicável
        logout(request)
        messages.error(request, "Tipo de usuário inválido para login.")
        return redirect("core:login")
    return _decide_post_login_redirect(request, user)


def _handle_tenant_selection_get(
    request: HttpRequest,
    tenant_id: str,
) -> HttpResponse:
    """Processa a seleção de tenant via método GET."""
    try:
        if request.user.is_superuser:
            tenant = Tenant.objects.get(id=tenant_id, status="active")
            request.session["tenant_id"] = tenant.id
            return redirect("dashboard")

        if Tenant.objects.filter(
            id=tenant_id,
            tenant_users__user=request.user,
            status="active",
        ).exists():
            request.session["tenant_id"] = tenant_id
            return redirect("dashboard")

        messages.error(request, "Você não tem acesso a essa empresa.")
    except Tenant.DoesNotExist:
        messages.error(request, "Empresa selecionada não encontrada.")
    except (ValueError, TypeError):
        messages.error(request, "ID de empresa inválido.")

    return redirect("core:tenant_select")


def _render_superuser_tenant_select(request: HttpRequest) -> HttpResponse:
    """Renderiza a página de seleção de tenant para superusuários."""
    all_tenants = Tenant.objects.filter(status="active").select_related(
        "pessoajuridica_info",
        "pessoafisica_info",
    )
    context = {
        "user_tenants": all_tenants,
        "page_title": "Seleção de Empresa (Opcional para Superusuário)",
        "is_superuser": True,
    }
    return render(request, "core/tenant_select.html", context)


def _handle_superuser_tenant_selection_post(
    request: HttpRequest,
) -> HttpResponse:
    """Processa a seleção de tenant para superusuários via POST."""
    tenant_id = request.POST.get("tenant_id")
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            request.session["tenant_id"] = tenant.id
        except (Tenant.DoesNotExist, ValueError, TypeError):
            pass  # Ignora se o ID for inválido
    return redirect("core:core_home")


def _handle_regular_user_tenant_selection(
    request: HttpRequest,
) -> HttpResponse:
    """Gerencia a seleção de tenant para usuários não-superusuários."""
    user_tenants = Tenant.objects.filter(
        tenant_users__user=request.user,
        status="active",
    ).select_related("pessoajuridica_info", "pessoafisica_info")

    if not user_tenants.exists():
        logout(request)
        messages.error(request, "Usuário não possui acesso a nenhuma empresa ativa.")
        return redirect("core:login")

    if user_tenants.count() == 1:
        tenant = user_tenants.first()
        if tenant:
            request.session["tenant_id"] = tenant.id
        return redirect("dashboard")

    if request.method == "POST":
        tenant_id = request.POST.get("tenant_id")
        if tenant_id and user_tenants.filter(id=tenant_id).exists():
            request.session["tenant_id"] = tenant_id
            return redirect("dashboard")
        messages.error(request, "Empresa selecionada inválida.")

    context = {
        "user_tenants": user_tenants,
        "page_title": "Seleção de Empresa",
    }
    return render(request, "core/tenant_select.html", context)


@login_required
def tenant_select(request: HttpRequest) -> HttpResponse:
    """View para seleção de tenant quando usuário tem múltiplos acessos."""
    if request.method == "GET":
        tenant_id = request.GET.get("tenant_id")
        if tenant_id:
            return _handle_tenant_selection_get(request, tenant_id)

    if request.user.is_superuser:
        if request.method == "POST":
            return _handle_superuser_tenant_selection_post(request)
        return _render_superuser_tenant_select(request)

    return _handle_regular_user_tenant_selection(request)


def logout_view(request: HttpRequest) -> HttpResponse:
    """View para logout."""
    logout(request)
    messages.success(request, "Logout realizado com sucesso.")
    return redirect("core:login")


@login_required
def ui_permissions_json(request: HttpRequest) -> JsonResponse:
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


class TenantListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    SuperuserRequiredMixin,
    PageTitleMixin,
    ListView,
):
    """Lista e gerencia todos os Tenants (empresas) do sistema."""

    model = Tenant
    template_name = "core/tenant_list.html"
    page_title = "Gerenciamento de Empresas"
    context_object_name = "object_list"
    paginate_by = 20
    app_label = "core"
    model_name = "tenant"

    def get_queryset(self) -> QuerySet[Tenant]:
        """Aplica filtros de busca e status ao queryset de tenants."""
        queryset = Tenant.objects.all().order_by("-created_at")

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(razao_social__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cpf__icontains=search),
            )

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        tipo_pessoa = self.request.GET.get("tipo_pessoa")
        if tipo_pessoa:
            queryset = queryset.filter(tipo_pessoa=tipo_pessoa)

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona estatísticas e dados de contexto à view."""
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
            },
        )
        return context

    def get(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Processa a alteração de status de um tenant via GET."""
        if "change_status" in request.GET and "new_status" in request.GET:
            tenant_id = request.GET.get("change_status")
            new_status = request.GET.get("new_status")

            status_mapping = {
                "ativo": "active",
                "inativo": "inactive",
                "pendente": "suspended",
            }

            if new_status in status_mapping:
                try:
                    tenant = get_object_or_404(Tenant, id=tenant_id)
                    tenant.status = status_mapping[new_status]
                    tenant.save()
                    status_display = {
                        "active": "Ativo",
                        "inactive": "Inativo",
                        "suspended": "Pendente",
                    }
                    messages.success(
                        request,
                        f'Status da empresa "{tenant.name}" alterado para '
                        f'"{status_display.get(tenant.status)}" com sucesso!',
                    )
                except Tenant.DoesNotExist:
                    messages.error(request, "Empresa não encontrada.")
                except Exception as e:
                    logger.exception("Erro ao alterar status do tenant.")
                    messages.error(request, f"Erro ao alterar status: {e!s}")

            return redirect("core:tenant_list")

        return super().get(request, *args, **kwargs)


class TenantDetailView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    SuperuserRequiredMixin,
    DetailView,
):
    """Exibe os detalhes de um Tenant específico."""

    model = Tenant
    template_name = "core/tenant_detail.html"
    context_object_name = "tenant"
    app_label = "core"
    model_name = "tenant"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona dados relacionados ao tenant no contexto."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Detalhes da Empresa: {self.object.name}"
        context["endereco_principal"] = Endereco.objects.filter(
            tenant=self.object,
            tipo="PRINCIPAL",
        ).first()
        context["enderecos_adicionais"] = self.object.enderecos_adicionais.all()
        context["contatos"] = self.object.contatos.all()
        context["documentos"] = self.object.documentos.all()
        context["usuarios"] = self.object.tenant_users.select_related(
            "user",
            "role",
            "department",
        ).all()
        return context


class TenantDeleteView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    SuperuserRequiredMixin,
    DeleteView,
):
    """View para exclusão de um Tenant."""

    model = Tenant
    template_name = "core/tenant_confirm_delete.html"
    success_url = reverse_lazy("core:tenant_list")
    app_label = "core"
    model_name = "tenant"

    def delete(
        self,
        request: HttpRequest,
        *_args: Any,  # noqa: ANN401
        **_kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Executa a exclusão e adiciona uma mensagem de sucesso."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(request, f"Empresa '{self.object.name}' excluída com sucesso.")
        self.object.delete()
        return redirect(success_url)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def tenant_module_config(request: HttpRequest, pk: int) -> HttpResponse:
    """Configura os módulos ativos para um Tenant específico."""
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == "POST":
        form = ModuleConfigurationForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Configuração de módulos atualizada para '{tenant.name}'.",
            )
            return redirect("core:tenant_detail", pk=tenant.pk)
        messages.error(request, _("Por favor, corrija os erros no formulário."))
    else:
        initial_modules = []
        if isinstance(tenant.enabled_modules, str):
            with contextlib.suppress(json.JSONDecodeError):
                initial_modules = json.loads(tenant.enabled_modules)
        elif isinstance(tenant.enabled_modules, dict):
            initial_modules = tenant.enabled_modules.get("modules", [])

        form = ModuleConfigurationForm(
            initial={"enabled_modules": initial_modules},
            tenant=tenant,
        )

    context = {
        "page_title": f"Configurar Módulos - {tenant.name}",
        "tenant": tenant,
        "form": form,
    }
    return render(request, "core/tenant_module_config.html", context)


class CustomUserListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista todos os usuários globais do sistema."""

    model = CustomUser
    template_name = "core/user_list.html"
    context_object_name = "users"
    paginate_by = 20


class CustomUserCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Cria um novo usuário global no sistema."""

    model = CustomUser
    form_class = CustomUserForm
    template_name = "core/user_form.html"
    success_url = reverse_lazy("core:user_list")


class CustomUserUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Atualiza um usuário global existente."""

    model = CustomUser
    form_class = CustomUserForm
    template_name = "core/user_form.html"
    success_url = reverse_lazy("core:user_list")


class CustomUserDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Exclui um usuário global do sistema."""

    model = CustomUser
    template_name = "core/user_confirm_delete.html"
    success_url = reverse_lazy("core:user_list")

    def delete(
        self,
        request: HttpRequest,
        *_args: Any,  # noqa: ANN401
        **_kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Executa a exclusão do usuário."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(
            request,
            f"Usuário '{self.object.get_full_name() or self.object.username}' excluído com sucesso.",
        )
        self.object.delete()
        return redirect(success_url)


class RoleListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    ListView,
):
    """Lista os cargos (Roles) do tenant ou de todo o sistema."""

    model = Role
    template_name = "core/role_list.html"
    context_object_name = "objects"
    app_label = "core"
    model_name = "role"

    def get_queryset(self) -> QuerySet[Role]:
        """Filtra os cargos com base no usuário e nos parâmetros da query."""
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            queryset = Role.objects.all()
        else:
            queryset = Role.objects.filter(tenant=tenant)

        name = self.request.GET.get("name")
        if name:
            queryset = queryset.filter(name__icontains=name)

        description = self.request.GET.get("description")
        if description:
            queryset = queryset.filter(description__icontains=description)

        has_users = self.request.GET.get("has_users")
        if has_users == "true":
            queryset = queryset.filter(tenantuser__isnull=False).distinct()
        elif has_users == "false":
            queryset = queryset.filter(tenantuser__isnull=True)

        return queryset.order_by("name")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona estatísticas e contexto para a view."""
        context = super().get_context_data(**kwargs)
        context["roles"] = context.get("objects", [])
        tenant = get_current_tenant(self.request)

        if self.request.user.is_superuser:
            context["current_tenant"] = tenant
            context["showing_all_tenants"] = not tenant
            all_roles = Role.objects.all() if not tenant else Role.objects.filter(tenant=tenant)
        else:
            all_roles = Role.objects.filter(tenant=tenant)

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
                "subtitle": f"{(roles_with_users / total_roles * 100):.1f}%" if total_roles > 0 else "0%",
            },
            {
                "label": "Cargos Vagos",
                "value": roles_without_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": f"{(roles_without_users / total_roles * 100):.1f}%" if total_roles > 0 else "0%",
            },
            {
                "label": "Cargos Ativos",
                "value": active_roles,
                "icon": "fas fa-check-circle",
                "color": "info",
                "subtitle": f"{(active_roles / total_roles * 100):.1f}%" if total_roles > 0 else "0%",
            },
        ]

        return context


class RoleCreateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    CreateView,
):
    """View para criar um novo cargo."""

    model = Role
    form_class = RoleForm
    template_name = "core/role_form.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona o request e o tenant aos kwargs do formulário."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        if not self.request.user.is_superuser:
            kwargs["tenant"] = get_current_tenant(self.request)
        return kwargs

    def form_valid(self, form: RoleForm) -> HttpResponse:
        """Define o tenant para o cargo se o usuário não for superuser."""
        if not self.request.user.is_superuser:
            form.instance.tenant = get_current_tenant(self.request)
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona cargos recentes ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            context["recent_roles"] = Role.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_roles"] = Role.objects.filter(tenant=tenant).order_by(
                "-created_at",
            )[:3]
        return context


class RoleDeleteView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DeleteView,
):
    """View para excluir um cargo."""

    model = Role
    template_name = "core/role_confirm_delete.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_queryset(self) -> QuerySet[Role]:
        """Filtra os cargos pelo tenant do usuário."""
        return Role.objects.filter(tenant=get_current_tenant(self.request))

    def delete(
        self,
        request: HttpRequest,
        *_args: Any,  # noqa: ANN401
        **_kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Executa a exclusão do cargo."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(request, f"Papel '{self.object.name}' excluído com sucesso.")
        self.object.delete()
        return redirect(success_url)


class RoleDetailView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DetailView,
):
    """View para visualizar detalhes de um cargo."""

    model = Role
    template_name = "core/role_detail.html"
    context_object_name = "role"
    app_label = "core"
    model_name = "role"

    def get_queryset(self) -> QuerySet[Role]:
        """Filtra os cargos com base no usuário."""
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(tenant=get_current_tenant(self.request))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona usuários e permissões do cargo ao contexto."""
        context = super().get_context_data(**kwargs)
        role = self.get_object()
        context["tenant_users"] = TenantUser.objects.filter(role=role).select_related(
            "user",
            "department",
        )
        context["permissions"] = role.permissions.all().order_by(
            "content_type__app_label",
            "codename",
        )
        return context


def _get_permissions_by_app() -> dict[str, dict[str, QuerySet[Permission]]]:
    """Busca e agrupa todas as permissões por aplicativo e modelo."""
    content_types = ContentType.objects.all().order_by("app_label", "model")
    permissions_by_app: dict[str, dict[str, QuerySet[Permission]]] = {}

    for ct in content_types:
        app_label = ct.app_label
        permissions = Permission.objects.filter(content_type=ct).order_by("codename")
        if permissions.exists():
            if app_label not in permissions_by_app:
                permissions_by_app[app_label] = {}
            permissions_by_app[app_label][ct.model] = permissions

    return permissions_by_app


def _get_role_for_permission_management(
    request: HttpRequest,
    pk: int,
) -> Role | None:
    """Busca o cargo para gerenciamento de permissões, validando o acesso."""
    tenant = get_current_tenant(request)
    is_admin = request.user.is_superuser or (
        tenant
        and TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            is_tenant_admin=True,
        ).exists()
    )

    if not is_admin:
        messages.error(request, "Você não tem permissão para gerenciar permissões.")
        return None

    try:
        if request.user.is_superuser and not tenant:
            return Role.objects.get(pk=pk)
        return Role.objects.get(pk=pk, tenant=tenant)
    except Role.DoesNotExist:
        messages.error(request, "Cargo não encontrado.")
        return None


@login_required
@require_http_methods(["GET", "POST"])
def role_permissions(request: HttpRequest, pk: int) -> HttpResponse:
    """View para gerenciar permissões de um cargo."""
    role = _get_role_for_permission_management(request, pk)
    if not role:
        return redirect("core:role_list")

    if request.method == "POST":
        try:
            permission_ids = [int(pid) for pid in request.POST.getlist("permissions")]
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
            messages.success(
                request,
                f"Permissões do cargo '{role.name}' atualizadas com sucesso.",
            )
            return redirect("core:role_detail", pk=pk)
        except (ValueError, TypeError):
            messages.error(request, "IDs de permissão inválidos.")
            return redirect("core:role_permissions", pk=pk)

    context = {
        "role": role,
        "permissions_by_app": _get_permissions_by_app(),
        "current_permissions": list(role.permissions.values_list("id", flat=True)),
    }
    return render(request, "core/role_permissions.html", context)


@login_required
def switch_tenant(request: HttpRequest, tenant_id: int) -> HttpResponse:
    """View para trocar de tenant (empresa).

    Permite que usuários alternem entre diferentes empresas.
    """
    try:
        tenant = get_object_or_404(Tenant, id=tenant_id)
        can_switch = False

        if request.user.is_superuser:
            can_switch = True
        elif TenantUser.objects.filter(user=request.user, tenant=tenant).exists():
            if request.user.is_active:
                can_switch = True
            else:
                messages.error(request, "Sua conta está inativa.")
        else:
            messages.error(request, "Você não tem acesso a esta empresa.")

        if can_switch:
            request.session["tenant_id"] = tenant_id
            request.session.modified = True
            messages.success(request, f"Empresa alterada para: {tenant.name}")
            next_url = request.GET.get("next", reverse("dashboard"))
            return redirect(next_url)

    except Tenant.DoesNotExist:
        messages.error(request, "Empresa não encontrada.")
    except Exception as e:
        logger.exception("Erro ao trocar de empresa.")
        messages.error(request, f"Erro ao trocar de empresa: {e!s}")

    return redirect("core:tenant_select")


# ============================================================================
# VIEWS DE GERENCIAMENTO DE USUÁRIOS DO TENANT (TenantUser)
# ============================================================================


class TenantUserListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    ListView,
):
    """Lista os usuários vinculados a um tenant."""

    model = TenantUser
    template_name = "core/tenant_user_list.html"
    context_object_name = "objects"
    paginate_by = 25
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self) -> QuerySet[TenantUser]:
        """Filtra os usuários do tenant com base nos parâmetros de busca."""
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            queryset = TenantUser.objects.all().select_related(
                "user",
                "role",
                "department",
            )
        else:
            queryset = TenantUser.objects.filter(tenant=tenant).select_related(
                "user",
                "role",
                "department",
            )

        nome = self.request.GET.get("nome")
        if nome:
            queryset = queryset.filter(
                Q(user__first_name__icontains=nome)
                | Q(user__last_name__icontains=nome)
                | Q(user__username__icontains=nome),
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona estatísticas de usuários ao contexto."""
        context = super().get_context_data(**kwargs)
        context["tenant_users"] = context.get("objects", [])
        tenant = get_current_tenant(self.request)

        if self.request.user.is_superuser and not tenant:
            all_users = TenantUser.objects.all()
        else:
            all_users = TenantUser.objects.filter(tenant=tenant)

        total_users = all_users.count()
        active_users = all_users.filter(user__is_active=True).count()
        inactive_users = total_users - active_users
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
                "subtitle": f"{(active_users / total_users * 100):.1f}%" if total_users > 0 else "0%",
            },
            {
                "label": "Usuários Inativos",
                "value": inactive_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": f"{(inactive_users / total_users * 100):.1f}%" if total_users > 0 else "0%",
            },
            {
                "label": "Administradores",
                "value": admin_users,
                "icon": "fas fa-user-shield",
                "color": "warning",
                "subtitle": f"{(admin_users / total_users * 100):.1f}%" if total_users > 0 else "0%",
            },
        ]

        return context


class TenantUserCreateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    CreateView,
):
    """View para criar um novo vínculo de usuário com um tenant."""

    model = TenantUser
    form_class = TenantUserForm
    template_name = "core/tenant_user_form.html"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona request e tenant aos kwargs do formulário."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        if not self.request.user.is_superuser:
            kwargs["tenant"] = get_current_tenant(self.request)
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona vínculos recentes de usuários ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if self.request.user.is_superuser and not tenant:
            recent_tenant_users = TenantUser.objects.select_related(
                "user",
                "tenant",
                "role",
                "department",
            ).order_by(
                "-created_at",
            )[:5]
        else:
            recent_tenant_users = (
                TenantUser.objects.filter(tenant=tenant)
                .select_related("user", "role", "department")
                .order_by("-created_at")[:5]
            )

        context["recent_tenant_users"] = recent_tenant_users
        return context

    def form_valid(self, form: TenantUserForm) -> HttpResponse:
        """Define o tenant se o usuário não for superuser."""
        if not self.request.user.is_superuser:
            form.instance.tenant = get_current_tenant(self.request)
        return super().form_valid(form)


class TenantUserUpdateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    UpdateView,
):
    """View para atualizar o vínculo de um usuário com um tenant."""

    model = TenantUser
    form_class = TenantUserForm
    template_name = "core/tenant_user_form.html"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self) -> QuerySet[TenantUser]:
        """Filtra os vínculos de usuário com base no usuário logado."""
        if self.request.user.is_superuser:
            return TenantUser.objects.all()
        return TenantUser.objects.filter(tenant=get_current_tenant(self.request))

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona o tenant aos kwargs do formulário se não for superuser."""
        kwargs = super().get_form_kwargs()
        if not self.request.user.is_superuser:
            kwargs["tenant"] = get_current_tenant(self.request)
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona vínculos recentes de usuários ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if self.request.user.is_superuser and not tenant:
            recent_tenant_users = TenantUser.objects.select_related(
                "user",
                "tenant",
                "role",
                "department",
            ).order_by(
                "-created_at",
            )[:5]
        else:
            recent_tenant_users = (
                TenantUser.objects.filter(tenant=tenant)
                .select_related("user", "role", "department")
                .order_by("-created_at")[:5]
            )

        context["recent_tenant_users"] = recent_tenant_users
        return context

    def form_valid(self, form: TenantUserForm) -> HttpResponse:
        """Define o tenant se o usuário não for superuser."""
        if not self.request.user.is_superuser:
            form.instance.tenant = get_current_tenant(self.request)
        return super().form_valid(form)


class TenantUserDeleteView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DeleteView,
):
    """View para remover o vínculo de um usuário com um tenant."""

    model = TenantUser
    template_name = "core/tenant_user_confirm_delete.html"
    context_object_name = "tenant_user"
    success_url = reverse_lazy("core:tenant_user_list")
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self) -> QuerySet[TenantUser]:
        """Filtra os vínculos de usuário pelo tenant atual."""
        return TenantUser.objects.filter(
            tenant=get_current_tenant(self.request),
        ).select_related("user", "role", "department")


@login_required
def tenant_user_permissions(request: HttpRequest, pk: int) -> HttpResponse:
    """View para gerenciar permissões específicas do usuário."""
    tenant = get_current_tenant(request)
    is_admin = request.user.is_superuser or (
        tenant
        and TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            is_tenant_admin=True,
        ).exists()
    )

    if not is_admin:
        messages.error(request, "Você não tem permissão para gerenciar permissões.")
        return HttpResponseForbidden("Sem permissão")

    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)

    messages.info(
        request,
        "Gerenciamento de permissões para "
        f"{tenant_user.user.get_full_name() or tenant_user.user.username} "
        "será implementado em breve.",
    )

    return redirect("core:tenant_user_list")


@login_required
def tenant_user_toggle_status(request: HttpRequest, pk: int) -> HttpResponse:
    """Ativa ou desativa o status de um usuário."""
    tenant = get_current_tenant(request)
    is_admin = request.user.is_superuser or (
        tenant
        and TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            is_tenant_admin=True,
        ).exists()
    )

    if not is_admin:
        messages.error(request, "Você não tem permissão para alterar status.")
        return HttpResponseForbidden("Sem permissão")

    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)

    user_to_toggle = tenant_user.user
    user_to_toggle.is_active = not user_to_toggle.is_active
    user_to_toggle.save()

    status = "ativado" if user_to_toggle.is_active else "desativado"
    messages.success(
        request,
        f"Usuário {user_to_toggle.get_full_name() or user_to_toggle.username} foi {status}.",
    )

    return redirect("core:tenant_user_list")


@login_required
def tenant_user_reset_password(request: HttpRequest, pk: int) -> HttpResponse:
    """Reseta a senha de um usuário."""
    tenant = get_current_tenant(request)
    is_admin = request.user.is_superuser or (
        tenant
        and TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            is_tenant_admin=True,
        ).exists()
    )

    if not is_admin:
        messages.error(request, "Você não tem permissão para resetar senhas.")
        return HttpResponseForbidden("Sem permissão")

    if request.user.is_superuser:
        tenant_user = get_object_or_404(TenantUser, pk=pk)
    else:
        tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)

    messages.info(
        request,
        "Reset de senha para "
        f"{tenant_user.user.get_full_name() or tenant_user.user.username} "
        "será implementado em breve.",
    )

    return redirect("core:tenant_user_list")


class RoleUpdateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    UpdateView,
):
    """View para atualizar um cargo existente."""

    model = Role
    form_class = RoleForm
    template_name = "core/role_form.html"
    success_url = reverse_lazy("core:role_list")
    app_label = "core"
    model_name = "role"

    def get_queryset(self) -> QuerySet[Role]:
        """Filtra os cargos com base no usuário."""
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(tenant=get_current_tenant(self.request))

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona o tenant aos kwargs do formulário."""
        kwargs = super().get_form_kwargs()
        tenant = get_current_tenant(self.request)
        if not self.request.user.is_superuser or tenant:
            kwargs["tenant"] = tenant
        return kwargs

    def form_valid(self, form: RoleForm) -> HttpResponse:
        """Define o tenant se o usuário não for superuser."""
        if not self.request.user.is_superuser:
            form.instance.tenant = get_current_tenant(self.request)
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona cargos recentes ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            context["recent_roles"] = Role.objects.all().order_by("-created_at")[:3]
        else:
            context["recent_roles"] = Role.objects.filter(tenant=tenant).order_by(
                "-created_at",
            )[:3]
        return context


class TenantUserDetailView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DetailView,
):
    """Exibe os detalhes de um vínculo de usuário com um tenant."""

    model = TenantUser
    template_name = "core/tenant_user_detail.html"
    context_object_name = "tenant_user"
    app_label = "core"
    model_name = "tenantuser"

    def get_queryset(self) -> QuerySet[TenantUser]:
        """Filtra os vínculos com base no usuário."""
        if self.request.user.is_superuser:
            return TenantUser.objects.all()
        return TenantUser.objects.filter(tenant=get_current_tenant(self.request))


# ============================================================================
# VIEWS DE GERENCIAMENTO DE DEPARTAMENTOS
# ============================================================================


class DepartmentListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    ListView,
):
    """Lista os departamentos do tenant ou de todo o sistema."""

    model = Department
    template_name = "core/department_list.html"
    context_object_name = "object_list"
    app_label = "core"
    model_name = "department"

    def get_queryset(self) -> QuerySet[Department]:
        """Filtra os departamentos com base no usuário e na busca."""
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            queryset = Department.objects.all().select_related("tenant")
        else:
            queryset = Department.objects.filter(
                Q(tenant=tenant) | Q(tenant__isnull=True),
            ).select_related("tenant")

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search),
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona estatísticas de departamentos ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if self.request.user.is_superuser and not tenant:
            all_departments = Department.objects.all()
        else:
            all_departments = Department.objects.filter(
                Q(tenant=tenant) | Q(tenant__isnull=True),
            )

        total_departments = all_departments.count()
        departments_with_users = all_departments.filter(tenantuser__isnull=False).distinct().count()
        departments_without_users = total_departments - departments_with_users
        recent_departments = all_departments.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30),
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
                "subtitle": (
                    f"{(departments_with_users / total_departments * 100):.1f}%" if total_departments > 0 else "0%"
                ),
            },
            {
                "label": "Sem Usuários",
                "value": departments_without_users,
                "icon": "fas fa-user-times",
                "color": "secondary",
                "subtitle": (
                    f"{(departments_without_users / total_departments * 100):.1f}%" if total_departments > 0 else "0%"
                ),
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


class DepartmentCreateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    CreateView,
):
    """View para criar um novo departamento."""

    model = Department
    form_class = DepartmentForm
    template_name = "core/department_form.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona departamentos recentes ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            context["recent_departments"] = Department.objects.all().order_by(
                "-created_at",
            )[:3]
        else:
            context["recent_departments"] = Department.objects.filter(
                tenant=tenant,
            ).order_by(
                "-created_at",
            )[:3]
        return context

    def form_valid(self, form: DepartmentForm) -> HttpResponse:
        """Valida e salva o formulário do departamento."""
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser:
            form.instance.tenant = form.cleaned_data.get("tenant")
        else:
            if not tenant:
                form.add_error(
                    None,
                    "Nenhuma empresa ativa. Selecione uma antes de criar.",
                )
                return self.form_invalid(form)
            form.instance.tenant = tenant
        form.instance.full_clean()
        return super().form_valid(form)

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona o request aos kwargs do formulário."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class DepartmentUpdateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    UpdateView,
):
    """View para atualizar um departamento existente."""

    model = Department
    form_class = DepartmentForm
    template_name = "core/department_form.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona departamentos recentes ao contexto."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        if self.request.user.is_superuser and not tenant:
            context["recent_departments"] = Department.objects.all().order_by(
                "-created_at",
            )[:3]
        else:
            context["recent_departments"] = Department.objects.filter(
                tenant=tenant,
            ).order_by(
                "-created_at",
            )[:3]
        return context

    def get_form_kwargs(self) -> dict[str, Any]:
        """Retorna os kwargs para o formulário."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_queryset(self) -> QuerySet[Department]:
        """Filtra os departamentos com base no usuário."""
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=get_current_tenant(self.request))


class DepartmentDetailView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DetailView,
):
    """Exibe os detalhes de um departamento."""

    model = Department
    template_name = "core/department_detail.html"
    context_object_name = "department"
    app_label = "core"
    model_name = "department"

    def get_queryset(self) -> QuerySet[Department]:
        """Filtra os departamentos com base no usuário."""
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=get_current_tenant(self.request))


class DepartmentDeleteView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DeleteView,
):
    """View para excluir um departamento."""

    model = Department
    template_name = "core/department_confirm_delete.html"
    success_url = reverse_lazy("core:department_list")
    app_label = "core"
    model_name = "department"

    def get_queryset(self) -> QuerySet[Department]:
        """Filtra os departamentos com base no usuário."""
        if self.request.user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(tenant=get_current_tenant(self.request))

    def delete(
        self,
        request: HttpRequest,
        *_args: Any,  # noqa: ANN401
        **_kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Executa a exclusão do departamento."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(
            request,
            f"Departamento '{self.object.name}' excluído com sucesso.",
        )
        self.object.delete()
        return redirect(success_url)


# ============================================================================
# VIEWS DE DOCUMENTOS DA EMPRESA
# ============================================================================


class EmpresaDocumentoListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    ListView,
):
    """Lista os documentos de uma empresa."""

    model = EmpresaDocumento
    template_name = "core/empresa_documento_list.html"
    context_object_name = "documentos"
    app_label = "core"
    model_name = "empresadocumento"

    def get_queryset(self) -> QuerySet[EmpresaDocumento]:
        """Filtra os documentos pelo tenant atual."""
        return EmpresaDocumento.objects.filter(
            tenant=get_current_tenant(self.request),
        ).order_by("-data_upload")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona o tenant ao contexto."""
        context = super().get_context_data(**kwargs)
        context["tenant"] = get_current_tenant(self.request)
        return context


class EmpresaDocumentoCreateView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    FormView,
):
    """View para criar um novo documento para a empresa."""

    form_class = EmpresaDocumentoVersaoCreateForm
    template_name = "core/empresa_documento_form.html"
    app_label = "core"
    model_name = "empresadocumento"

    def get_success_url(self) -> str:
        """Retorna a URL de sucesso após a criação."""
        return reverse("core:empresa_documento_list")

    def get_form_kwargs(self) -> dict[str, Any]:
        """Adiciona o tenant aos kwargs do formulário."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = get_current_tenant(self.request)
        return kwargs

    def form_valid(self, form: EmpresaDocumentoVersaoCreateForm) -> HttpResponse:
        """Chama o método save do formulário com o usuário e redireciona."""
        try:
            # Garantir que o usuário é do tipo correto
            user = self.request.user
            if isinstance(user, CustomUser):
                form.save(user=user)
                messages.success(self.request, "Nova versão do documento criada com sucesso.")
            else:
                # Caso o usuário não seja do tipo esperado, ainda tenta salvar sem ele
                # ou lança um erro mais específico.
                form.save()
                messages.warning(
                    self.request,
                    "Documento criado, mas não foi possível associar o usuário.",
                )

        except ValueError as e:
            messages.error(self.request, f"Erro de valor ao criar o documento: {e}")
            return self.form_invalid(form)
        except Exception as e:
            logger.exception("Erro inesperado ao salvar o formulário de documento.")
            messages.error(self.request, f"Erro inesperado ao criar o documento: {e}")
            return self.form_invalid(form)

        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona o tenant ao contexto."""
        context = super().get_context_data(**kwargs)
        context["tenant"] = get_current_tenant(self.request)
        return context


class EmpresaDocumentoDetailView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DetailView,
):
    """Exibe os detalhes de um documento da empresa."""

    model = EmpresaDocumento
    template_name = "core/empresa_documento_detail.html"
    context_object_name = "documento"
    app_label = "core"
    model_name = "empresadocumento"

    def get_queryset(self) -> QuerySet[EmpresaDocumento]:
        """Filtra os documentos pelo tenant atual."""
        return EmpresaDocumento.objects.filter(tenant=get_current_tenant(self.request))


class EmpresaDocumentoDeleteView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    DeleteView,
):
    """View para excluir um documento da empresa."""

    model = EmpresaDocumento
    template_name = "core/empresa_documento_confirm_delete.html"
    context_object_name = "documento"
    app_label = "core"
    model_name = "empresadocumento"

    def get_success_url(self) -> str:
        """Retorna a URL de sucesso após a exclusão."""
        return reverse("core:empresa_documento_list")

    def get_queryset(self) -> QuerySet[EmpresaDocumento]:
        """Filtra os documentos pelo tenant atual."""
        return EmpresaDocumento.objects.filter(tenant=get_current_tenant(self.request))

    def delete(
        self,
        request: HttpRequest,
        *_args: Any,  # noqa: ANN401
        **_kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Executa a exclusão do documento."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        messages.success(
            request,
            f"Documento '{self.object.nome_documento}' excluído com sucesso.",
        )
        self.object.delete()
        return redirect(success_url)


class ItemAuxiliarListView(
    UIPermissionsMixin,
    LoginRequiredMixin,
    TenantAdminOrSuperuserMixin,
    ListView,
):
    """Lista os itens auxiliares."""

    model = ItemAuxiliar
    template_name = "core/itemauxiliar_list.html"
    context_object_name = "itens"
    paginate_by = 20
    app_label = "cadastros_gerais"
    model_name = "itemauxiliar"

    def get_queryset(self) -> QuerySet[ItemAuxiliar]:
        """Filtra os itens auxiliares com base na busca."""
        queryset = ItemAuxiliar.objects.all().order_by("tipo", "descricao")
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(tipo__icontains=search_query) | Q(descricao__icontains=search_query),
            )
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona a query de busca ao contexto."""
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        return context

"""Módulo de administração para o sistema Pandora."""

from __future__ import annotations

import logging
from datetime import timedelta
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet, Sum
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import Cliente
from core.models import Tenant, TenantUser
from core.utils import get_current_tenant
from financeiro.models import ContaPagar, ContaReceber
from funcionarios.models import Funcionario
from obras.models import Obra
from orcamentos.models import Orcamento
from produtos.models import Produto
from user_management.models import PerfilUsuarioEstendido

from .forms import (
    SystemAlertForm,
    SystemConfigurationForm,
    TenantConfigurationForm,
)
from .models import (
    AdminActivity,
    SystemAlert,
    SystemConfiguration,
    TenantBackup,
    TenantConfiguration,
)
from .serializers import (
    AdminActivitySerializer,
    DashboardStatsSerializer,
    SystemAlertSerializer,
    SystemConfigurationSerializer,
    TenantBackupSerializer,
    TenantConfigurationSerializer,
    TenantUsageReportSerializer,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django.forms import BaseModelForm

User = get_user_model()
logger = logging.getLogger(__name__)


class ModuleInfo(TypedDict):
    """Define a estrutura para as informações do módulo."""

    id: str
    name: str
    description: str
    icon: str
    category: str
    price: float
    active: bool
    usage: float


# --- Views de Página (Renderizadas com Templates) ---


@login_required
def admin_home(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """View ultra-moderna para o dashboard administrativo com métricas em tempo real.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse renderizando o dashboard ou um redirecionamento.

    """
    template_name = "admin/admin_home.html"
    tenant = get_current_tenant(request)

    # Estatísticas baseadas no perfil do usuário
    if request.user.is_superuser:
        # Super Admin: Dados globais do sistema
        # Métricas principais
        total_empresas = Tenant.objects.count()
        empresas_ativas = Tenant.objects.filter(status="active").count()
        usuarios_sistema = PerfilUsuarioEstendido.objects.count()
        usuarios_ativos = PerfilUsuarioEstendido.objects.filter(
            status="ativo",
        ).count()

        # Alertas e notificações
        alertas_criticos = SystemAlert.objects.filter(
            severity="critical",
            status="open",
        ).count()
        alertas_pendentes = SystemAlert.objects.filter(status="open").count()
        alertas_resolvidos_hoje = SystemAlert.objects.filter(
            status="resolved",
            resolved_at__date=timezone.now().date(),
        ).count()

        # Atividades administrativas recentes
        atividades_recentes = AdminActivity.objects.select_related(
            "admin_user",
            "tenant",
        ).order_by(
            "-created_at"
        )[:10]

        # Métricas de performance
        performance_geral = 98.5  # Simulado - implementar cálculo real
        uptime_sistema = 99.9  # Simulado - implementar cálculo real

        # Dados para gráficos
        alertas_por_severidade = {
            "critical": SystemAlert.objects.filter(severity="critical").count(),
            "high": SystemAlert.objects.filter(severity="high").count(),
            "medium": SystemAlert.objects.filter(severity="medium").count(),
            "low": SystemAlert.objects.filter(severity="low").count(),
        }

        context_specific = {
            "empresas_ativas": empresas_ativas,
            "usuarios_sistema": usuarios_sistema,
            "usuarios_ativos": usuarios_ativos,
            "alertas_criticos": alertas_criticos,
            "alertas_por_severidade": alertas_por_severidade,
            "performance_geral": performance_geral,
            "uptime_sistema": uptime_sistema,
            "can_manage_system": True,
        }

    else:
        # Admin da empresa: Dados específicos da empresa
        if not tenant:
            messages.error(
                request,
                _("Selecione uma empresa para ver o dashboard."),
            )
            return redirect(reverse("core:tenant_select"))

        # Métricas da empresa
        tenant_users = TenantUser.objects.filter(tenant=tenant)
        total_empresas = 1  # Sempre 1 para admin da empresa
        empresas_ativas = 1 if tenant.status == "active" else 0
        usuarios_sistema = tenant_users.count()
        usuarios_ativos = PerfilUsuarioEstendido.objects.filter(
            user__in=tenant_users.values_list("user", flat=True),
            status="ativo",
        ).count()

        # Alertas específicos da empresa
        alertas_criticos = SystemAlert.objects.filter(
            tenant=tenant,
            severity="critical",
            status="open",
        ).count()
        alertas_pendentes = SystemAlert.objects.filter(
            tenant=tenant,
            status="open",
        ).count()
        alertas_resolvidos_hoje = SystemAlert.objects.filter(
            tenant=tenant,
            status="resolved",
            resolved_at__date=timezone.now().date(),
        ).count()

        # Atividades da empresa
        atividades_recentes = (
            AdminActivity.objects.filter(tenant=tenant).select_related("admin_user").order_by("-created_at")[:10]
        )

        # Performance da empresa
        performance_geral = 95.0  # Simulado
        uptime_sistema = 99.5  # Simulado

        # Dados para gráficos (específicos da empresa)
        alertas_por_severidade = {
            "critical": SystemAlert.objects.filter(
                tenant=tenant,
                severity="critical",
            ).count(),
            "high": SystemAlert.objects.filter(
                tenant=tenant,
                severity="high",
            ).count(),
            "medium": SystemAlert.objects.filter(
                tenant=tenant,
                severity="medium",
            ).count(),
            "low": SystemAlert.objects.filter(
                tenant=tenant,
                severity="low",
            ).count(),
        }

        context_specific = {
            "empresas_ativas": empresas_ativas,
            "usuarios_sistema": usuarios_sistema,
            "usuarios_ativos": usuarios_ativos,
            "alertas_criticos": alertas_criticos,
            "alertas_por_severidade": alertas_por_severidade,
            "performance_geral": performance_geral,
            "uptime_sistema": uptime_sistema,
            "can_manage_system": False,
        }

    # Contexto comum
    context = {
        "titulo": _("Dashboard Administrativo"),
        "subtitulo": _("Painel de controle e monitoramento"),
        "tenant": tenant,
        "total_empresas": total_empresas,
        "alertas_pendentes": alertas_pendentes,
        "alertas_resolvidos_hoje": alertas_resolvidos_hoje,
        "atividades_recentes": atividades_recentes,
        "is_superuser": request.user.is_superuser,
        # Dados para widgets modernos
        "widgets_data": {
            "alertas_resumo": {
                "total": alertas_pendentes,
                "criticos": alertas_criticos,
                "resolvidos_hoje": alertas_resolvidos_hoje,
            },
            "sistema_performance": {
                "geral": performance_geral,
                "uptime": uptime_sistema,
            },
        },
        # Configurações do dashboard
        "dashboard_config": {
            "auto_refresh": True,
            "refresh_interval": 300000,  # 5 minutos
            "show_notifications": True,
            "enable_dark_mode": (
                request.user.perfilusuarioestendido.tema_escuro
                if hasattr(request.user, "perfilusuarioestendido")
                else False
            ),
        },
    }

    # Adicionar dados específicos do tipo de usuário
    context.update(context_specific)

    return render(request, template_name, context)


@login_required
def alerts_page(request: HttpRequest) -> HttpResponse:
    """View moderna para listar alertas com filtros avançados.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse renderizando a lista de alertas.

    """
    template_name = "admin/alerts_list.html"

    # Filtros
    severity_filter = request.GET.get("severity", "")
    tenant_filter = request.GET.get("tenant", "")
    status_filter = request.GET.get("status", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Query base
    alerts = SystemAlert.objects.select_related(
        "tenant",
        "assigned_to",
    ).order_by("-created_at")

    # Aplicar filtros
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)
    if tenant_filter:
        alerts = alerts.filter(tenant_id=tenant_filter)
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    if date_from:
        alerts = alerts.filter(created_at__date__gte=date_from)
    if date_to:
        alerts = alerts.filter(created_at__date__lte=date_to)

    # Se não for superuser, filtrar por tenants acessíveis
    if not request.user.is_superuser:
        tenant = get_current_tenant(request)
        alerts = alerts.filter(tenant=tenant) if tenant else alerts.none()

    # Paginação
    paginator = Paginator(alerts, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "alerts": page_obj,
        "tenants": Tenant.objects.filter(status="active").order_by("name"),
        "severity_filter": severity_filter,
        "tenant_filter": tenant_filter,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "total_alerts": paginator.count,
        "page_title": "Alertas do Sistema",
        "page_subtitle": "Monitore e gerencie alertas de segurança e performance",
    }

    return render(request, template_name, context)


@login_required
def configurations_page(request: HttpRequest) -> HttpResponse:
    """View moderna para configurações do sistema.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse renderizando a página de configurações.

    """
    template_name = "admin/configurations_list.html"

    # Filtros
    category_filter = request.GET.get("category", "")
    search_query = request.GET.get("search", "")

    # Query base
    configs = SystemConfiguration.objects.order_by("category", "key")

    # Aplicar filtros
    if category_filter:
        configs = configs.filter(category=category_filter)
    if search_query:
        configs = configs.filter(
            Q(key__icontains=search_query) | Q(description__icontains=search_query),
        )

    # Agrupar por categoria
    configs_by_category = {category: list(group) for category, group in groupby(configs, key=lambda x: x.category)}

    context = {
        "configurations": configs,
        "configs_by_category": configs_by_category,
        "categories": configs.values_list("category", flat=True).distinct(),
        "category_filter": category_filter,
        "search_query": search_query,
        "page_title": "Configurações do Sistema",
        "page_subtitle": "Gerencie configurações globais do sistema",
    }

    return render(request, template_name, context)


class SystemAlertCreateView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    CreateView,
):
    """View para criar novos alertas do sistema."""

    model = SystemAlert
    form_class = SystemAlertForm
    template_name = "admin/system_alert_form.html"
    success_url = reverse_lazy("administration:alerts_page")

    def test_func(self) -> bool:
        """Verifica se o usuário é superuser."""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Novo Alerta do Sistema",
                "page_subtitle": "Criar um novo alerta para monitoramento",
                "form_title": "Informações do Alerta",
            },
        )
        return context

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        """Executa se o formulário for válido."""
        messages.success(self.request, "Alerta criado com sucesso!")
        return super().form_valid(form)


class SystemAlertUpdateView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    UpdateView,
):
    """View para editar alertas do sistema."""

    model = SystemAlert
    form_class = SystemAlertForm
    template_name = "admin/system_alert_form.html"
    success_url = reverse_lazy("administration:alerts_page")

    def test_func(self) -> bool:
        """Verifica se o usuário é superuser."""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Editar Alerta: {self.object.title}",
                "page_subtitle": "Atualize as informações do alerta",
                "form_title": "Informações do Alerta",
            },
        )
        return context

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        """Executa se o formulário for válido."""
        messages.success(self.request, "Alerta atualizado com sucesso!")
        return super().form_valid(form)


class SystemConfigurationCreateView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    CreateView,
):
    """View para criar configurações globais do sistema."""

    model = SystemConfiguration
    form_class = SystemConfigurationForm
    template_name = "admin/system_config_form.html"
    success_url = reverse_lazy("administration:configurations_page")

    def test_func(self) -> bool:
        """Verifica se o usuário é superuser."""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Nova Configuração do Sistema",
                "page_subtitle": "Criar uma nova configuração global",
                "form_title": "Informações da Configuração",
            },
        )
        return context

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        """Executa se o formulário for válido."""
        messages.success(self.request, "Configuração criada com sucesso!")
        return super().form_valid(form)


class SystemConfigurationUpdateView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    UpdateView,
):
    """View para editar configurações globais do sistema."""

    model = SystemConfiguration
    form_class = SystemConfigurationForm
    template_name = "admin/system_config_form.html"
    success_url = reverse_lazy("administration:configurations_page")

    def test_func(self) -> bool:
        """Verifica se o usuário é superuser."""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Editar Configuração: {self.object.key}",
                "page_subtitle": "Atualize a configuração do sistema",
                "form_title": "Informações da Configuração",
            },
        )
        return context

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        """Executa se o formulário for válido."""
        messages.success(self.request, "Configuração atualizada com sucesso!")
        return super().form_valid(form)


class TenantConfigurationUpdateView(LoginRequiredMixin, UpdateView):
    """View para editar configurações da empresa."""

    model = TenantConfiguration
    form_class = TenantConfigurationForm
    template_name = "admin/tenant_config_form.html"
    success_url = reverse_lazy("administration:configurations_page")

    def get_object(
        self,
        queryset: QuerySet[TenantConfiguration] | None = None,
    ) -> TenantConfiguration:
        """Pega ou cria a configuração do tenant atual."""
        _ = queryset  # Unused argument
        tenant = get_current_tenant(self.request)
        if not tenant:
            msg = "Nenhuma empresa selecionada"
            raise Http404(msg)

        config, _created = TenantConfiguration.objects.get_or_create(
            tenant=tenant,
            defaults={
                "max_users": 100,
                "max_storage_mb": 1024,
                "max_api_requests_per_hour": 1000,
                "require_2fa": False,
                "backup_enabled": True,
                "custom_branding": {},
            },
        )
        return config

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        context.update(
            {
                "page_title": f"Configurações - {tenant.name if tenant else ''}",
                "page_subtitle": "Configure os parâmetros da empresa",
                "form_title": "Configurações da Empresa",
                "current_tenant": tenant,
            },
        )
        return context

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        """Executa se o formulário for válido."""
        messages.success(
            self.request,
            "Configurações da empresa atualizadas com sucesso!",
        )
        return super().form_valid(form)


class SystemAlertListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View para listar alertas do sistema."""

    model = SystemAlert
    template_name = "admin/system_alerts.html"
    context_object_name = "alerts"
    paginate_by = 20

    def test_func(self) -> bool:
        """Verifica se o usuário é superuser."""
        return self.request.user.is_superuser

    def get_queryset(self) -> QuerySet[SystemAlert]:
        """Retorna a queryset de alertas filtrada."""
        queryset = SystemAlert.objects.all().order_by("-created_at")

        # Filtros
        status = self.request.GET.get("status")
        severity = self.request.GET.get("severity")
        tenant_id = self.request.GET.get("tenant")

        if status:
            queryset = queryset.filter(status=status)
        if severity:
            queryset = queryset.filter(severity=severity)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        return queryset

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Alertas do Sistema",
                "page_subtitle": "Monitoramento e gestão de alertas",
                "tenants": Tenant.objects.filter(status="active").order_by(
                    "name",
                ),
                "status_choices": SystemAlert.STATUS_CHOICES,
                "severity_choices": SystemAlert.SEVERITY_CHOICES,
            },
        )
        return context


class AdminDashboardView(TemplateView):
    """Dashboard principal do Super Admin com estatísticas e alertas."""

    template_name = "admin/dashboard_ultra_modern.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Painel do Super Admin"
        return context


class SystemAlertsView(TemplateView):
    """Página para visualizar e gerenciar alertas do sistema."""

    template_name = "admin/system_alerts_ultra_modern.html"


class SystemConfigurationsView(TemplateView):
    """Página para configurações LOCAIS da empresa (tenant)."""

    template_name = "admin/tenant_configurations.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)

        # Pegar o tenant atual
        tenant = get_current_tenant(self.request)
        if not tenant:
            return context

        context.update(
            {
                "page_title": f"Configurações da Empresa - {tenant.name}",
                "page_subtitle": "Configurações e personalizações específicas da empresa",
                "current_tenant": tenant,
                # Configurações da empresa
                "tenant_configs": {
                    "company_name": tenant.name,
                    "company_type": tenant.get_tipo_pessoa_display(),
                    "cnpj_cpf": tenant.cnpj or tenant.cpf,
                    "status": tenant.status,
                    "enabled_modules": tenant.enabled_modules,
                    "created_at": tenant.created_at,
                },
            },
        )

        return context


class ManagementDashboardView(TemplateView):
    """Dashboard de Gestão Empresarial Ultra-Moderno."""

    template_name = "management_home.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """Adiciona dados ao contexto do template."""
        context = super().get_context_data(**kwargs)

        # Dados gerais do sistema
        context.update(
            {
                "page_title": "Dashboard de Gestão Empresarial",
                "page_subtitle": "Painel de controle e monitoramento empresarial",
                # Métricas principais
                "total_funcionarios": self.get_total_funcionarios(),
                "pendencias_criticas": self.get_pendencias_criticas(),
                "performance_geral": self.get_performance_geral(),
                "tarefas_vencidas": self.get_tarefas_vencidas(),
                # Dados para gráficos
                "performance_departamentos": self.get_performance_departamentos(),
                "chart_labels": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun"],
                "chart_data": self.get_monthly_performance(),
                # KPIs e estatísticas
                "kpis_principais": self.get_kpis_principais(),
                "team_performance": self.get_team_performance(),
                "recent_activities": self.get_recent_activities(),
                # Configurações de dashboard
                "dashboard_config": {
                    "auto_refresh": True,
                    "refresh_interval": 30,
                    "theme": "professional",
                    "layout": "management",
                },
            },
        )

        return context

    def get_total_funcionarios(self) -> int:
        """Retorna o total de funcionários ativos."""
        try:
            return Funcionario.objects.filter(ativo=True).count()
        except ImportError:
            logger.warning("Módulo 'funcionarios' não encontrado. Usando valor mock.")
            return 156  # Valor fictício para demonstração

    def get_pendencias_criticas(self) -> int:
        """Retorna o número de pendências críticas."""
        pendencias = 0
        try:
            # Contas a pagar vencidas
            contas_vencidas = ContaPagar.objects.filter(
                status="pendente",
                data_vencimento__lt=timezone.now().date(),
            ).count()
            pendencias += contas_vencidas

            # Obras com problemas
            obras_problemas = Obra.objects.filter(
                status__in=["parada", "atrasada"],
            ).count()
            pendencias += obras_problemas

        except ImportError as e:
            logger.warning("Erro ao importar módulo para pendências: %s", e)
            return 12  # Valor fictício
        return pendencias

    def get_performance_geral(self) -> int:
        """Calcula a performance geral do sistema."""
        try:
            # Lógica para calcular performance baseada em KPIs
            # Exemplo: média de diferentes métricas
            produtividade = 87
            qualidade = 92
            eficiencia = 73
            pontualidade = 89

            performance = (produtividade + qualidade + eficiencia + pontualidade) / 4
            return round(performance)
        except Exception:
            logger.exception("Erro ao calcular performance geral")
            return 87

    def get_tarefas_vencidas(self) -> int:
        """Retorna o número de tarefas vencidas."""
        try:
            # Integração com sistema de tarefas se existir
            return 8  # Valor fictício
        except Exception:
            logger.exception("Erro ao buscar tarefas vencidas")
            return 8

    def get_performance_departamentos(self) -> list[int]:
        """Retorna performance por departamento para gráfico radar."""
        return [85, 92, 78, 88, 91, 87]

    def get_monthly_performance(self) -> list[int]:
        """Retorna dados de performance mensal."""
        return [78, 82, 85, 83, 89, 87]

    def get_kpis_principais(self) -> dict[str, dict[str, Any]]:
        """Retorna os KPIs principais."""
        return {
            "produtividade": {
                "value": 87,
                "target": 85,
                "status": "success",
                "trend": "up",
            },
            "qualidade": {
                "value": 92,
                "target": 90,
                "status": "success",
                "trend": "up",
            },
            "eficiencia": {
                "value": 73,
                "target": 80,
                "status": "warning",
                "trend": "down",
            },
            "pontualidade": {
                "value": 89,
                "target": 85,
                "status": "success",
                "trend": "up",
            },
        }

    def get_team_performance(self) -> list[dict[str, Any]]:
        """Retorna dados de performance da equipe."""
        try:
            return [
                {
                    "nome": func.nome,
                    "email": func.email,
                    "departamento": getattr(func, "departamento", "Geral"),
                    "performance": 75 + (hash(func.nome) % 25),
                    "tarefas_concluidas": 10 + (hash(func.nome) % 10),
                    "tarefas_total": 15,
                    "status": "online" if hash(func.nome) % 3 == 0 else "busy",
                }
                for func in Funcionario.objects.filter(ativo=True)[:10]
            ]
        except ImportError:
            logger.warning("Módulo 'funcionarios' não encontrado. Usando dados mock.")
            # Dados fictícios para demonstração
            return [
                {
                    "nome": "João Silva",
                    "email": "joao@empresa.com",
                    "departamento": "Vendas",
                    "performance": 92,
                    "tarefas_concluidas": 18,
                    "tarefas_total": 20,
                    "status": "online",
                },
                {
                    "nome": "Maria Santos",
                    "email": "maria@empresa.com",
                    "departamento": "Financeiro",
                    "performance": 88,
                    "tarefas_concluidas": 15,
                    "tarefas_total": 16,
                    "status": "busy",
                },
                {
                    "nome": "Pedro Costa",
                    "email": "pedro@empresa.com",
                    "departamento": "Produção",
                    "performance": 79,
                    "tarefas_concluidas": 12,
                    "tarefas_total": 15,
                    "status": "online",
                },
            ]

    def get_recent_activities(self) -> list[dict[str, Any]]:
        """Retorna atividades recentes do sistema."""
        try:
            # Últimos logins
            recent_users = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(hours=24),
            ).order_by(
                "-last_login"
            )[:5]

            return [
                {
                    "user": user,
                    "title": f"{user.first_name} fez login",
                    "description": "Acesso ao sistema",
                    "timestamp": user.last_login,
                    "priority": "low",
                    "status": "online",
                }
                for user in recent_users
            ]
        except Exception:
            logger.exception("Erro ao buscar atividades recentes")
            # Atividades fictícias
            return [
                {
                    "user": type("User", (), {"first_name": "Admin", "avatar": None})(),
                    "title": "Backup realizado",
                    "description": "Backup automático do sistema concluído",
                    "timestamp": timezone.now(),
                    "priority": "medium",
                    "status": "online",
                },
                {
                    "user": type(
                        "User",
                        (),
                        {"first_name": "Sistema", "avatar": None},
                    )(),
                    "title": "Relatório gerado",
                    "description": "Relatório mensal de performance",
                    "timestamp": timezone.now() - timedelta(minutes=30),
                    "priority": "low",
                    "status": "online",
                },
            ]


# --- API ViewSets (para alimentar o dashboard e outras funcionalidades) ---


class DashboardStatsViewSet(viewsets.ViewSet):
    """Fornece estatísticas agregadas para o dashboard do super admin."""

    permission_classes: ClassVar[list] = [permissions.IsAdminUser]

    def list(self, request: HttpRequest) -> Response:
        """Agrega dados de todo o sistema para o super admin.

        Args:
            request: O objeto HttpRequest.

        Returns:
            Uma Response com os dados serializados.

        """
        _ = request  # Unused argument
        total_tenants = Tenant.objects.count()
        total_users = User.objects.count()
        total_clientes = Cliente.objects.count()
        total_produtos = Produto.objects.count()
        total_obras = Obra.objects.count()
        total_orcamentos = Orcamento.objects.count()

        total_a_pagar = (
            ContaPagar.objects.filter(status="pendente").aggregate(
                total=Sum("valor"),
            )["total"]
            or 0
        )
        total_a_receber = (
            ContaReceber.objects.filter(status="pendente").aggregate(
                total=Sum("valor"),
            )["total"]
            or 0
        )

        # NOVO: Contagem de alertas abertos
        open_alerts = SystemAlert.objects.filter(status="open").count()

        data = {
            "total_tenants": total_tenants,
            "total_users": total_users,
            "total_clientes": total_clientes,
            "total_produtos": total_produtos,
            "total_obras": total_obras,
            "total_orcamentos": total_orcamentos,
            "total_a_pagar": total_a_pagar,
            "total_a_receber": total_a_receber,
            "open_alerts": open_alerts,  # Adicionado ao dicionário
        }

        serializer = DashboardStatsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class SystemAlertViewSet(viewsets.ModelViewSet):
    """API para gerenciar alertas do sistema."""

    queryset = SystemAlert.objects.all()
    serializer_class = SystemAlertSerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]


class TenantConfigurationViewSet(viewsets.ModelViewSet):
    """API para gerenciar configurações específicas de um tenant."""

    queryset = TenantConfiguration.objects.all()
    serializer_class = TenantConfigurationSerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]


class AdminActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """API para visualizar logs de atividade do admin."""

    queryset = AdminActivity.objects.all().order_by("-created_at")
    serializer_class = AdminActivitySerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]


class SystemConfigurationViewSet(viewsets.ModelViewSet):
    """API para gerenciar configurações globais do sistema."""

    queryset = SystemConfiguration.objects.all()
    serializer_class = SystemConfigurationSerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]


class TenantBackupViewSet(viewsets.ModelViewSet):
    """API para gerenciar backups dos tenants."""

    queryset = TenantBackup.objects.all()
    serializer_class = TenantBackupSerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]


class TenantUsageReportViewSet(viewsets.ReadOnlyModelViewSet):
    """API para gerar relatórios de uso dos tenants."""

    serializer_class = TenantUsageReportSerializer
    permission_classes: ClassVar[list] = [permissions.IsAdminUser]

    def get_queryset(self) -> QuerySet[Tenant]:
        """Gera dados do relatório de uso.

        Returns:
            QuerySet de Tenants anotado com dados de uso.

        """
        return Tenant.objects.annotate(
            num_users=Count("user"),
            num_obras=Count("obras"),
        )


class TenantListLiteView(APIView):
    """Lista simplificada de tenants (nome e subdomínio) usada por testes antigos.

    Mantida para compatibilidade durante transição; quando estabilizado pode ser
    substituída por endpoint mais completo versionado.
    """

    permission_classes: ClassVar[list] = [permissions.IsAdminUser]

    def get(self, request: HttpRequest) -> Response:
        qs = Tenant.objects.order_by("name").values("id", "name", "subdomain")[:200]
        return Response(list(qs))


# --- Novas Views para Completar o Módulo Admin ---


@login_required
def modules_page(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """View para gerenciar módulos contratados pela empresa.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse ou um redirecionamento.

    """
    template_name = "admin/modules_dashboard.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Selecione uma empresa para ver os módulos."))
        return redirect(reverse("core:tenant_select"))

    # Módulos disponíveis no sistema (simulado)
    available_modules: list[ModuleInfo] = [
        {
            "id": "obras",
            "name": "Gestão de Obras",
            "description": "Controle completo de obras e projetos",
            "icon": "fas fa-building",
            "category": "Operacional",
            "price": 149.90,
            "active": True,
            "usage": 85.2,
        },
        {
            "id": "financeiro",
            "name": "Financeiro",
            "description": "Contas a pagar, receber e fluxo de caixa",
            "icon": "fas fa-dollar-sign",
            "category": "Financeiro",
            "price": 99.90,
            "active": True,
            "usage": 92.5,
        },
        {
            "id": "estoque",
            "name": "Controle de Estoque",
            "description": "Gestão de materiais e produtos",
            "icon": "fas fa-boxes",
            "category": "Operacional",
            "price": 79.90,
            "active": True,
            "usage": 67.8,
        },
        {
            "id": "rh",
            "name": "Recursos Humanos",
            "description": "Gestão de funcionários e folha de pagamento",
            "icon": "fas fa-users",
            "category": "Administrativo",
            "price": 129.90,
            "active": False,
            "usage": 0,
        },
        {
            "id": "bi",
            "name": "Business Intelligence",
            "description": "Relatórios avançados e análises",
            "icon": "fas fa-chart-bar",
            "category": "Análise",
            "price": 199.90,
            "active": False,
            "usage": 0,
        },
        {
            "id": "crm",
            "name": "CRM",
            "description": "Gestão de relacionamento com clientes",
            "icon": "fas fa-handshake",
            "category": "Comercial",
            "price": 89.90,
            "active": True,
            "usage": 74.3,
        },
    ]

    # Estatísticas dos módulos
    active_modules = [m for m in available_modules if m["active"]]
    total_monthly_cost = sum(m["price"] for m in active_modules)
    average_usage = sum(m["usage"] for m in active_modules) / len(active_modules) if active_modules else 0

    context = {
        "modules": available_modules,
        "active_modules": active_modules,
        "total_modules": len(available_modules),
        "active_count": len(active_modules),
        "inactive_count": len(available_modules) - len(active_modules),
        "total_monthly_cost": total_monthly_cost,
        "average_usage": average_usage,
        "tenant": tenant,
        "page_title": "Módulos Contratados",
        "page_subtitle": "Gerencie os módulos e serviços da sua empresa",
    }

    return render(request, template_name, context)


@login_required
def reports_page(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """View para relatórios e métricas da empresa.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse ou um redirecionamento.

    """
    template_name = "admin/reports_dashboard.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Selecione uma empresa para ver os relatórios."))
        return redirect(reverse("core:tenant_select"))

    # Período para os relatórios
    period = request.GET.get("period", "30")  # 30, 90, 365 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=int(period))

    # Relatórios disponíveis
    reports = [
        {
            "id": "users_activity",
            "title": "Atividade de Usuários",
            "description": "Acompanhe o engajamento dos usuários",
            "icon": "fas fa-users-cog",
            "color": "primary",
            "value": "87%",
            "change": "+12%",
            "trend": "up",
        },
        {
            "id": "storage_usage",
            "title": "Uso de Armazenamento",
            "description": "Monitoramento do espaço utilizado",
            "icon": "fas fa-database",
            "color": "info",
            "value": "65.2 GB",
            "change": "+5.2 GB",
            "trend": "up",
        },
        {
            "id": "system_performance",
            "title": "Performance do Sistema",
            "description": "Velocidade e disponibilidade",
            "icon": "fas fa-tachometer-alt",
            "color": "success",
            "value": "99.8%",
            "change": "+0.2%",
            "trend": "up",
        },
        {
            "id": "security_events",
            "title": "Eventos de Segurança",
            "description": "Monitoramento de segurança",
            "icon": "fas fa-shield-alt",
            "color": "warning",
            "value": "3",
            "change": "-2",
            "trend": "down",
        },
    ]

    # Métricas mensais (simulado)
    monthly_metrics = {
        "usuarios_ativos": 45,
        "modulos_utilizados": 6,
        "transacoes_processadas": 1250,
        "tempo_resposta_medio": "1.2s",
        "disponibilidade": "99.8%",
        "storage_usado": "65.2 GB",
    }

    context = {
        "reports": reports,
        "monthly_metrics": monthly_metrics,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "tenant": tenant,
        "page_title": "Relatórios e Métricas",
        "page_subtitle": "Analise o desempenho e uso da sua empresa",
    }

    return render(request, template_name, context)


@login_required
def billing_page(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """View para plano e faturamento da empresa.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse ou um redirecionamento.

    """
    template_name = "admin/billing_dashboard.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Selecione uma empresa para ver o faturamento."))
        return redirect(reverse("core:tenant_select"))

    # Informações do plano atual (simulado)
    current_plan = {
        "name": "Plano Profissional",
        "price": 599.90,
        "billing_cycle": "monthly",
        "users_included": 50,
        "storage_included": "100 GB",
        "modules_included": 8,
        "support_level": "Premium",
        "next_billing_date": timezone.now().date() + timedelta(days=15),
    }

    # Histórico de faturas (simulado)
    invoices = [
        {
            "id": "INV-2025-001",
            "date": timezone.now().date() - timedelta(days=30),
            "amount": 599.90,
            "status": "paid",
            "due_date": timezone.now().date() - timedelta(days=25),
            "description": "Plano Profissional - Janeiro 2025",
        },
        {
            "id": "INV-2024-012",
            "date": timezone.now().date() - timedelta(days=60),
            "amount": 599.90,
            "status": "paid",
            "due_date": timezone.now().date() - timedelta(days=55),
            "description": "Plano Profissional - Dezembro 2024",
        },
        {
            "id": "INV-2024-011",
            "date": timezone.now().date() - timedelta(days=90),
            "amount": 549.90,
            "status": "paid",
            "due_date": timezone.now().date() - timedelta(days=85),
            "description": "Plano Profissional - Novembro 2024",
        },
    ]

    # Uso atual vs limites
    usage_stats = {
        "users": {"current": 32, "limit": 50, "percentage": 64},
        "storage": {"current": 65.2, "limit": 100, "percentage": 65.2},
        "modules": {"current": 6, "limit": 8, "percentage": 75},
        "api_calls": {"current": 8500, "limit": 10000, "percentage": 85},
    }

    # Planos disponíveis para upgrade
    available_plans = [
        {
            "name": "Básico",
            "price": 299.90,
            "users": 20,
            "storage": "50 GB",
            "modules": 5,
            "support": "Padrão",
            "current": False,
        },
        {
            "name": "Profissional",
            "price": 599.90,
            "users": 50,
            "storage": "100 GB",
            "modules": 8,
            "support": "Premium",
            "current": True,
        },
        {
            "name": "Empresarial",
            "price": 999.90,
            "users": 100,
            "storage": "250 GB",
            "modules": 12,
            "support": "Priority",
            "current": False,
        },
    ]

    context = {
        "current_plan": current_plan,
        "invoices": invoices,
        "usage_stats": usage_stats,
        "available_plans": available_plans,
        "tenant": tenant,
        "page_title": "Plano e Faturamento",
        "page_subtitle": "Gerencie sua assinatura e pagamentos",
    }

    return render(request, template_name, context)


@login_required
def support_page(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """View para suporte técnico e tickets.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse ou um redirecionamento.

    """
    template_name = "admin/support_dashboard.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Selecione uma empresa para acessar o suporte."))
        return redirect(reverse("core:tenant_select"))

    # Tickets do suporte (simulado)
    tickets = [
        {
            "id": "TK-2025-001",
            "title": "Problema no módulo financeiro",
            "status": "open",
            "priority": "high",
            "category": "bug",
            "created_at": timezone.now() - timedelta(hours=2),
            "last_update": timezone.now() - timedelta(minutes=30),
            "assigned_to": "João Silva",
            "description": "Relatório de contas a receber não está gerando corretamente",
        },
        {
            "id": "TK-2025-002",
            "title": "Solicitação de novo usuário",
            "status": "closed",
            "priority": "low",
            "category": "request",
            "created_at": timezone.now() - timedelta(days=1),
            "last_update": timezone.now() - timedelta(hours=5),
            "assigned_to": "Ana Souza",
            "description": "Adicionar novo usuário 'carlos.pereira' ao sistema.",
        },
    ]

    faqs = [
        {
            "question": "Como resetar minha senha?",
            "answer": "Você pode resetar sua senha na tela de login...",
        },
        {
            "question": "Como gerar um relatório de vendas?",
            "answer": "Vá para o módulo de Vendas, clique em Relatórios...",
        },
    ]

    context = {
        "tickets": tickets,
        "faqs": faqs,
        "open_tickets": sum(1 for t in tickets if t["status"] == "open"),
        "closed_tickets": sum(1 for t in tickets if t["status"] == "closed"),
        "tenant": tenant,
        "page_title": "Suporte Técnico",
        "page_subtitle": "Acesse a ajuda, documentação e abra tickets de suporte",
    }

    return render(request, template_name, context)

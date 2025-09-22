# core/home_system.py
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from .models import Department, Role, Tenant, TenantUser


class CoreHomeSystem:
    """
    Sistema de Home do Módulo CORE
    Responsável por gerenciar empresas, usuários e configurações do sistema
    """

    def __init__(self, user=None):
        self.user = user

    def get_home_context(self):
        """
        Retorna todos os dados necessários para o home do CORE
        """
        context = {}

        # Métricas principais
        context.update(self._get_metrics())

        # Dados para gráficos
        context.update(self._get_chart_data())

        # Listas para widgets
        context.update(self._get_widget_lists())

        return context

    def _get_metrics(self):
        """Calcula as métricas principais do home"""
        try:
            # Contagem de tenants
            total_tenants = Tenant.objects.count()
            active_tenants = Tenant.objects.filter(status="active").count()

            # Contagem de usuários associados a tenants (mais relevante para o dashboard do Core)
            total_users = TenantUser.objects.count()

            # Contagem de cargos e departamentos
            total_roles = Role.objects.count()
            total_departamentos = Department.objects.count()

            # Cálculo estimado de MRR (Monthly Recurring Revenue)
            # Assumindo um valor base por tenant ativo
            mrr_value = active_tenants * 500  # R$ 500 por tenant ativo

            return {
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "total_users": total_users,
                "total_roles": total_roles,
                "total_departamentos": total_departamentos,
                "mrr_value": mrr_value,
            }
        except Exception:
            # Em caso de erro, retorna valores padrão
            return {
                "total_tenants": 0,
                "active_tenants": 0,
                "total_users": 0,
                "total_roles": 0,
                "total_departamentos": 0,
                "mrr_value": 0,
            }

    def _get_chart_data(self):
        """Prepara dados para os gráficos"""
        import json

        try:
            # Dados para gráfico de crescimento de tenants (últimos 6 meses)
            tenant_growth_data = self._get_tenant_growth_data()

            # Dados para gráfico de status de tenants
            tenant_status_data = self._get_tenant_status_data()

            return {
                "tenant_growth_labels": json.dumps(tenant_growth_data["labels"]),
                "tenant_growth_data": json.dumps(tenant_growth_data["data"]),
                "tenant_status_labels": json.dumps(tenant_status_data["labels"]),
                "tenant_status_data": json.dumps(tenant_status_data["data"]),
            }
        except Exception:
            # Em caso de erro, retorna dados vazios
            import json

            return {
                "tenant_growth_labels": json.dumps([]),
                "tenant_growth_data": json.dumps([]),
                "tenant_status_labels": json.dumps([]),
                "tenant_status_data": json.dumps([]),
            }

    def _get_tenant_growth_data(self):
        """Calcula dados de crescimento de tenants nos últimos 6 meses"""
        now = timezone.now()
        labels = []
        data = []

        for i in range(6):
            # Calcula o mês
            date = now - relativedelta(months=i)
            month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)

            # Conta tenants criados neste mês
            count = Tenant.objects.filter(created_at__gte=month_start, created_at__lte=month_end).count()

            # Adiciona aos dados
            labels.insert(0, date.strftime("%b/%Y"))
            data.insert(0, count)

        return {"labels": labels, "data": data}

    def _get_tenant_status_data(self):
        """Calcula distribuição de status dos tenants"""
        try:
            active_count = Tenant.objects.filter(status="active").count()
            inactive_count = Tenant.objects.filter(status="inactive").count()

            return {"labels": ["Ativos", "Inativos"], "data": [active_count, inactive_count]}
        except Exception:
            return {"labels": ["Ativos", "Inativos"], "data": [0, 0]}

    def _get_widget_lists(self):
        """Prepara listas para widgets"""
        try:
            # Tenants recentes (últimos 5)
            recent_tenants = Tenant.objects.select_related().order_by("-created_at")[:5]

            return {
                "recent_tenants": recent_tenants,
            }
        except Exception:
            return {
                "recent_tenants": [],
            }


class HomeMetrics:
    """
    Classe utilitária para cálculos de métricas específicas
    """

    @staticmethod
    def calculate_growth_percentage(current, previous):
        """Calcula percentual de crescimento"""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    @staticmethod
    def format_currency(value):
        """Formata valor monetário"""
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def get_trend_indicator(percentage):
        """Retorna indicador de tendência baseado no percentual"""
        if percentage > 0:
            return "positive"
        elif percentage < 0:
            return "negative"
        else:
            return "neutral"

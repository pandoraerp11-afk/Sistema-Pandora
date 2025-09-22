# core/dashboard_widgets.py
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import CustomUser, Department, Role, Tenant


class BaseDashboardWidget:
    """
    Classe base para todos os widgets do dashboard
    """

    def __init__(self, request=None):
        self.request = request
        self.user = request.user if request else None

    def get_data(self):
        """Método que deve ser implementado pelos widgets filhos"""
        raise NotImplementedError("Widgets devem implementar o método get_data()")

    def has_permission(self):
        """Verifica se o usuário tem permissão para ver este widget"""
        return True  # Por padrão, todos podem ver


class TenantMetricsWidget(BaseDashboardWidget):
    """
    Widget para métricas de empresas/tenants
    """

    def get_data(self):
        """Retorna dados das métricas de tenants"""
        try:
            total = Tenant.objects.count()
            active = Tenant.objects.filter(status="active").count()
            inactive = Tenant.objects.filter(status="inactive").count()

            # Crescimento mensal
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month = Tenant.objects.filter(created_at__gte=month_start).count()

            last_month_start = month_start - timedelta(days=month_start.day)
            last_month_end = month_start - timedelta(seconds=1)
            last_month = Tenant.objects.filter(created_at__gte=last_month_start, created_at__lte=last_month_end).count()

            growth = self._calculate_growth(this_month, last_month)

            return {
                "total": total,
                "active": active,
                "inactive": inactive,
                "this_month": this_month,
                "growth_percentage": growth,
                "trend": "positive" if growth > 0 else "negative" if growth < 0 else "neutral",
            }
        except Exception:
            return {"total": 0, "active": 0, "inactive": 0, "this_month": 0, "growth_percentage": 0, "trend": "neutral"}

    def _calculate_growth(self, current, previous):
        """Calcula percentual de crescimento"""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)


class UserMetricsWidget(BaseDashboardWidget):
    """
    Widget para métricas de usuários
    """

    def get_data(self):
        """Retorna dados das métricas de usuários"""
        try:
            total_users = CustomUser.objects.count()
            active_users = CustomUser.objects.filter(is_active=True).count()
            superusers = CustomUser.objects.filter(is_superuser=True).count()

            # Usuários criados nos últimos 30 dias
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_users = CustomUser.objects.filter(date_joined__gte=thirty_days_ago).count()

            return {
                "total": total_users,
                "active": active_users,
                "superusers": superusers,
                "recent": recent_users,
            }
        except Exception:
            return {
                "total": 0,
                "active": 0,
                "superusers": 0,
                "recent": 0,
            }


class RoleMetricsWidget(BaseDashboardWidget):
    """
    Widget para métricas de cargos/roles
    """

    def get_data(self):
        """Retorna dados das métricas de cargos"""
        try:
            total_roles = Role.objects.count()
            active_roles = Role.objects.filter(is_active=True).count()

            # Cargos por tenant (se aplicável)
            roles_by_tenant = (
                Role.objects.values("tenant__razao_social").annotate(count=Count("id")).order_by("-count")[:5]
            )

            return {
                "total": total_roles,
                "active": active_roles,
                "by_tenant": list(roles_by_tenant),
            }
        except Exception:
            return {
                "total": 0,
                "active": 0,
                "by_tenant": [],
            }


class DepartmentMetricsWidget(BaseDashboardWidget):
    """
    Widget para métricas de departamentos
    """

    def get_data(self):
        """Retorna dados das métricas de departamentos"""
        try:
            total_departments = Department.objects.count()
            active_departments = Department.objects.filter(is_active=True).count()

            return {
                "total": total_departments,
                "active": active_departments,
            }
        except Exception:
            return {
                "total": 0,
                "active": 0,
            }


class RecentActivityWidget(BaseDashboardWidget):
    """
    Widget para atividades recentes
    """

    def get_data(self):
        """Retorna dados de atividades recentes"""
        try:
            # Tenants recentes
            recent_tenants = Tenant.objects.select_related().order_by("-created_at")[:5]

            # Usuários recentes
            recent_users = CustomUser.objects.select_related().order_by("-date_joined")[:5]

            return {
                "recent_tenants": recent_tenants,
                "recent_users": recent_users,
            }
        except Exception:
            return {
                "recent_tenants": [],
                "recent_users": [],
            }


class QuickActionsWidget(BaseDashboardWidget):
    """
    Widget para ações rápidas do módulo CORE
    """

    def get_data(self):
        """Retorna dados para ações rápidas"""
        actions = [
            {
                "title": "Nova Empresa",
                "icon": "fas fa-plus",
                "url": "core:tenant_create",
                "color": "primary",
                "permission": "core.add_tenant",
            },
            {
                "title": "Gerenciar Empresas",
                "icon": "fas fa-building",
                "url": "core:tenant_list",
                "color": "secondary",
                "permission": "core.view_tenant",
            },
            {
                "title": "Gerenciar Usuários",
                "icon": "fas fa-users",
                "url": "user_management:usuario_list",
                "color": "info",
                "permission": "user_management.view_usuario",
            },
            {
                "title": "Gerenciar Cargos",
                "icon": "fas fa-user-tag",
                "url": "core:role_list",
                "color": "warning",
                "permission": "core.view_role",
            },
        ]

        # Filtra ações baseado nas permissões do usuário
        if self.user:
            filtered_actions = []
            for action in actions:
                if not action.get("permission") or self.user.has_perm(action["permission"]):
                    filtered_actions.append(action)
            return {"actions": filtered_actions}

        return {"actions": actions}


class ChartDataWidget(BaseDashboardWidget):
    """
    Widget para dados de gráficos
    """

    def get_tenant_growth_chart_data(self):
        """Retorna dados para gráfico de crescimento de tenants"""
        try:
            from dateutil.relativedelta import relativedelta

            now = timezone.now()
            labels = []
            data = []

            for i in range(6):
                date = now - relativedelta(months=i)
                month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)

                count = Tenant.objects.filter(created_at__gte=month_start, created_at__lte=month_end).count()

                labels.insert(0, date.strftime("%b/%Y"))
                data.insert(0, count)

            return {"labels": labels, "data": data, "type": "bar"}
        except Exception:
            return {"labels": [], "data": [], "type": "bar"}

    def get_tenant_status_chart_data(self):
        """Retorna dados para gráfico de status de tenants"""
        try:
            active_count = Tenant.objects.filter(status="active").count()
            inactive_count = Tenant.objects.filter(status="inactive").count()

            return {
                "labels": ["Ativos", "Inativos"],
                "data": [active_count, inactive_count],
                "type": "doughnut",
                "colors": ["#22c55e", "#f59e0b"],
            }
        except Exception:
            return {
                "labels": ["Ativos", "Inativos"],
                "data": [0, 0],
                "type": "doughnut",
                "colors": ["#22c55e", "#f59e0b"],
            }


# Classe principal para gerenciar todos os widgets
class CoreDashboardWidgets:
    """
    Gerenciador de todos os widgets do dashboard do CORE
    """

    def __init__(self, request=None):
        self.request = request
        self.widgets = {
            "tenant_metrics": TenantMetricsWidget(request),
            "user_metrics": UserMetricsWidget(request),
            "role_metrics": RoleMetricsWidget(request),
            "department_metrics": DepartmentMetricsWidget(request),
            "recent_activity": RecentActivityWidget(request),
            "quick_actions": QuickActionsWidget(request),
            "chart_data": ChartDataWidget(request),
        }

    def get_all_widget_data(self):
        """Retorna dados de todos os widgets"""
        data = {}

        for widget_name, widget_instance in self.widgets.items():
            if widget_instance.has_permission():
                try:
                    data[widget_name] = widget_instance.get_data()
                except Exception:
                    # Em caso de erro, adiciona dados vazios
                    data[widget_name] = {}

        return data

# admin/utils.py (VERSÃO MELHORADA)

import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import models
from django.utils import timezone

from .models import AdminActivity, SystemAlert, TenantMetrics

logger = logging.getLogger(__name__)


def log_admin_activity(
    user,
    action,
    resource_type,
    resource_id="",
    description="",
    request=None,
    tenant=None,
    before_data=None,
    after_data=None,
):
    """
    Registra uma atividade administrativa no sistema.

    Args:
        user: Usuário que executou a ação
        action: Tipo de ação ('create', 'update', 'delete', 'view', 'backup', 'restore')
        resource_type: Tipo do recurso afetado
        resource_id: ID do recurso (opcional)
        description: Descrição da atividade
        request: Objeto request do Django (para capturar IP)
        tenant: Tenant afetado (opcional)
        before_data: Dados antes da alteração (opcional)
        after_data: Dados após a alteração (opcional)
    """
    try:
        ip_address = None
        if request:
            # Tenta obter o IP real considerando proxies
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            ip_address = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

        AdminActivity.objects.create(
            admin_user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else "",
            tenant=tenant,
            description=description,
            ip_address=ip_address,
            before_data=before_data or {},
            after_data=after_data or {},
        )

        logger.info(f"Atividade registrada: {user} - {action} em {resource_type}")

    except Exception as e:
        logger.error(f"Erro ao registrar atividade administrativa: {e}")


def get_system_health_summary():
    """
    Retorna um resumo da saúde do sistema com métricas importantes.
    Utiliza cache para melhorar performance.
    """
    cache_key = "system_health_summary"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    try:
        from core.models import CustomUser, Tenant

        # Métricas básicas
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()

        # Métricas de usuários
        total_users = CustomUser.objects.count()
        active_users = CustomUser.objects.filter(is_active=True).count()

        # Alertas críticos
        critical_alerts = SystemAlert.objects.filter(severity="critical", status__in=["open", "acknowledged"]).count()

        # Métricas de performance dos últimos 7 dias
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_metrics = TenantMetrics.objects.filter(date__gte=seven_days_ago.date()).aggregate(
            avg_response_time=models.Avg("response_time_avg"),
            avg_uptime=models.Avg("uptime"),
            total_api_requests=models.Sum("api_requests"),
            avg_error_rate=models.Avg("error_rate"),
        )

        # Calcula tendências
        current_week_tenants = Tenant.objects.filter(created_at__gte=seven_days_ago).count()

        previous_week_start = seven_days_ago - timedelta(days=7)
        previous_week_tenants = Tenant.objects.filter(
            created_at__gte=previous_week_start, created_at__lt=seven_days_ago
        ).count()

        tenant_growth_rate = 0
        if previous_week_tenants > 0:
            tenant_growth_rate = ((current_week_tenants - previous_week_tenants) / previous_week_tenants) * 100

        health_data = {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_users": total_users,
            "active_users": active_users,
            "critical_alerts": critical_alerts,
            "avg_response_time": round(recent_metrics.get("avg_response_time", 0) or 0, 2),
            "avg_uptime": round(recent_metrics.get("avg_uptime", 100) or 100, 2),
            "total_api_requests": recent_metrics.get("total_api_requests", 0) or 0,
            "avg_error_rate": round(recent_metrics.get("avg_error_rate", 0) or 0, 2),
            "tenant_growth_rate": round(tenant_growth_rate, 2),
            "current_week_tenants": current_week_tenants,
            "system_status": "healthy" if critical_alerts == 0 else "warning" if critical_alerts < 5 else "critical",
        }

        # Cache por 5 minutos
        cache.set(cache_key, health_data, 300)

        return health_data

    except Exception as e:
        logger.error(f"Erro ao obter resumo de saúde do sistema: {e}")
        return {
            "total_tenants": 0,
            "active_tenants": 0,
            "total_users": 0,
            "active_users": 0,
            "critical_alerts": 0,
            "avg_response_time": 0,
            "avg_uptime": 100,
            "total_api_requests": 0,
            "avg_error_rate": 0,
            "tenant_growth_rate": 0,
            "current_week_tenants": 0,
            "system_status": "unknown",
        }


def create_system_alert(title, description, severity="medium", alert_type="system", tenant=None, metadata=None):
    """
    Cria um alerta do sistema.

    Args:
        title: Título do alerta
        description: Descrição detalhada
        severity: Severidade ('low', 'medium', 'high', 'critical')
        alert_type: Tipo do alerta
        tenant: Tenant relacionado (opcional)
        metadata: Dados adicionais (opcional)
    """
    try:
        alert = SystemAlert.objects.create(
            title=title,
            description=description,
            severity=severity,
            alert_type=alert_type,
            tenant=tenant,
            metadata=metadata or {},
        )

        logger.warning(f"Alerta criado: {title} - Severidade: {severity}")

        # Se for crítico, pode disparar notificações adicionais
        if severity == "critical":
            # Aqui você pode adicionar lógica para notificações urgentes
            # como envio de emails, webhooks, etc.
            pass

        return alert

    except Exception as e:
        logger.error(f"Erro ao criar alerta do sistema: {e}")
        return None


def get_tenant_usage_stats(tenant, days=30):
    """
    Retorna estatísticas de uso de um tenant específico.

    Args:
        tenant: Instância do Tenant
        days: Número de dias para análise (padrão: 30)
    """
    try:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        metrics = TenantMetrics.objects.filter(tenant=tenant, date__range=[start_date, end_date]).aggregate(
            avg_active_users=models.Avg("active_users"),
            max_active_users=models.Max("active_users"),
            total_storage_used=models.Sum("storage_used"),
            total_api_requests=models.Sum("api_requests"),
            avg_response_time=models.Avg("response_time_avg"),
            avg_uptime=models.Avg("uptime"),
            avg_error_rate=models.Avg("error_rate"),
        )

        # Calcula tendências
        mid_date = start_date + timedelta(days=days // 2)

        first_half = TenantMetrics.objects.filter(tenant=tenant, date__range=[start_date, mid_date]).aggregate(
            avg_users=models.Avg("active_users")
        )

        second_half = TenantMetrics.objects.filter(tenant=tenant, date__range=[mid_date, end_date]).aggregate(
            avg_users=models.Avg("active_users")
        )

        user_trend = 0
        if first_half["avg_users"] and second_half["avg_users"]:
            user_trend = ((second_half["avg_users"] - first_half["avg_users"]) / first_half["avg_users"]) * 100

        return {
            "period_days": days,
            "avg_active_users": round(metrics.get("avg_active_users", 0) or 0, 1),
            "max_active_users": metrics.get("max_active_users", 0) or 0,
            "total_storage_used_mb": round((metrics.get("total_storage_used", 0) or 0) / (1024 * 1024), 2),
            "total_api_requests": metrics.get("total_api_requests", 0) or 0,
            "avg_response_time": round(metrics.get("avg_response_time", 0) or 0, 2),
            "avg_uptime": round(metrics.get("avg_uptime", 100) or 100, 2),
            "avg_error_rate": round(metrics.get("avg_error_rate", 0) or 0, 2),
            "user_trend_percent": round(user_trend, 2),
        }

    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de uso do tenant {tenant}: {e}")
        return {}


def cleanup_old_data(days_to_keep=90):
    """
    Remove dados antigos para manter o banco de dados limpo.

    Args:
        days_to_keep: Número de dias de dados para manter
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Remove métricas antigas
        old_metrics = TenantMetrics.objects.filter(created_at__lt=cutoff_date)
        metrics_count = old_metrics.count()
        old_metrics.delete()

        # Remove atividades administrativas antigas (exceto as críticas)
        old_activities = AdminActivity.objects.filter(created_at__lt=cutoff_date).exclude(
            action__in=["delete", "backup", "restore"]  # Mantém ações importantes
        )
        activities_count = old_activities.count()
        old_activities.delete()

        # Remove alertas resolvidos antigos
        old_alerts = SystemAlert.objects.filter(created_at__lt=cutoff_date, status="resolved")
        alerts_count = old_alerts.count()
        old_alerts.delete()

        logger.info(
            f"Limpeza concluída: {metrics_count} métricas, {activities_count} atividades, {alerts_count} alertas removidos"
        )

        return {
            "metrics_removed": metrics_count,
            "activities_removed": activities_count,
            "alerts_removed": alerts_count,
        }

    except Exception as e:
        logger.error(f"Erro durante limpeza de dados antigos: {e}")
        return {}


def validate_system_configuration(key, value):
    """
    Valida configurações do sistema antes de salvar.

    Args:
        key: Chave da configuração
        value: Valor a ser validado

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Validações específicas por tipo de configuração
        if key == "max_upload_size":
            if not isinstance(value, (int, float)) or value <= 0:
                return False, "Tamanho máximo de upload deve ser um número positivo"
            if value > 100 * 1024 * 1024:  # 100MB
                return False, "Tamanho máximo de upload não pode exceder 100MB"

        elif key == "smtp_port":
            if not isinstance(value, int) or value <= 0 or value > 65535:
                return False, "Porta SMTP deve ser um número entre 1 e 65535"

        elif key == "backup_retention_days":
            if not isinstance(value, int) or value < 1:
                return False, "Dias de retenção de backup deve ser pelo menos 1"
            if value > 365:
                return False, "Dias de retenção de backup não pode exceder 365"

        elif key == "smtp_host":
            if not isinstance(value, str) or len(value.strip()) == 0:
                return False, "Host SMTP não pode estar vazio"

        elif key == "site_name":
            if not isinstance(value, str) or len(value.strip()) == 0:
                return False, "Nome do site não pode estar vazio"
            if len(value) > 100:
                return False, "Nome do site não pode exceder 100 caracteres"

        return True, ""

    except Exception as e:
        logger.error(f"Erro ao validar configuração {key}: {e}")
        return False, "Erro interno de validação"

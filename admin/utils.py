# admin/utils.py (VERSÃO FINAL CORRIGIDA)
"""Utilitários para o painel de administração.

Este módulo fornece funções auxiliares para o painel de administração,
incluindo registro de atividades, monitoramento de saúde do sistema,
gerenciamento de alertas, estatísticas de uso e validação de configurações.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from django.contrib.auth.models import AbstractBaseUser
from django.core.cache import cache
from django.db import models, transaction
from django.http import HttpRequest
from django.utils import timezone

from .models import AdminActivity, SystemAlert, Tenant, TenantMetrics

logger = logging.getLogger(__name__)

# Constantes para valores mágicos
MAX_UPLOAD_SIZE_MB = 100
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_SMTP_PORT = 65535
MAX_BACKUP_RETENTION_DAYS = 365
MAX_SITE_NAME_LENGTH = 100
CRITICAL_ALERT_THRESHOLD = 5
HEALTH_SUMMARY_CACHE_TTL_SECONDS = 300


@dataclass
class AdminActivityLog:
    """Estrutura para dados de log de atividade administrativa."""

    user: AbstractBaseUser
    action: Literal["create", "update", "delete", "view", "backup", "restore"]
    resource_type: str
    resource_id: str = ""
    description: str = ""
    request: HttpRequest | None = None
    tenant: Tenant | None = None
    before_data: dict | None = None
    after_data: dict | None = None


def log_admin_activity(log_data: AdminActivityLog) -> None:
    """Registra uma atividade administrativa no sistema.

    Args:
        log_data: Objeto com os dados da atividade a ser registrada.

    """
    try:
        ip_address = None
        if log_data.request:
            x_forwarded_for = log_data.request.META.get("HTTP_X_FORWARDED_FOR")
            ip_address = (
                x_forwarded_for.split(",")[0].strip() if x_forwarded_for else log_data.request.META.get("REMOTE_ADDR")
            )

        AdminActivity.objects.create(
            admin_user=log_data.user,
            action=log_data.action,
            resource_type=log_data.resource_type,
            resource_id=str(log_data.resource_id) if log_data.resource_id else "",
            tenant=log_data.tenant,
            description=log_data.description,
            ip_address=ip_address,
            before_data=log_data.before_data or {},
            after_data=log_data.after_data or {},
        )
        logger.info(
            "Atividade registrada: %s - %s em %s",
            log_data.user,
            log_data.action,
            log_data.resource_type,
        )
    except (AttributeError, TypeError, ValueError):
        logger.exception("Erro ao registrar atividade administrativa")


def get_system_health_summary() -> dict[str, Any]:
    """Retorna um resumo da saúde do sistema com métricas importantes.

    Utiliza cache para melhorar a performance.

    Returns:
        Dicionário com dados de saúde do sistema.

    """
    cache_key = "system_health_summary"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    try:
        from core.models import CustomUser  # noqa: PLC0415 - Importação local para evitar ciclos

        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        total_users = CustomUser.objects.count()
        active_users = CustomUser.objects.filter(is_active=True).count()
        critical_alerts = SystemAlert.objects.filter(
            severity="critical",
            status__in=["open", "acknowledged"],
        ).count()

        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_metrics = TenantMetrics.objects.filter(
            date__gte=seven_days_ago.date(),
        ).aggregate(
            avg_response_time=models.Avg("response_time_avg"),
            avg_uptime=models.Avg("uptime"),
            total_api_requests=models.Sum("api_requests"),
            avg_error_rate=models.Avg("error_rate"),
        )

        current_week_tenants = Tenant.objects.filter(
            created_at__gte=seven_days_ago,
        ).count()
        previous_week_start = seven_days_ago - timedelta(days=7)
        previous_week_tenants = Tenant.objects.filter(
            created_at__gte=previous_week_start,
            created_at__lt=seven_days_ago,
        ).count()

        tenant_growth_rate = (
            ((current_week_tenants - previous_week_tenants) / previous_week_tenants) * 100
            if previous_week_tenants > 0
            else 0
        )

        health_data = {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_users": total_users,
            "active_users": active_users,
            "critical_alerts": critical_alerts,
            "avg_response_time": round(
                recent_metrics.get("avg_response_time") or 0,
                2,
            ),
            "avg_uptime": round(recent_metrics.get("avg_uptime") or 100, 2),
            "total_api_requests": recent_metrics.get("total_api_requests") or 0,
            "avg_error_rate": round(recent_metrics.get("avg_error_rate") or 0, 2),
            "tenant_growth_rate": round(tenant_growth_rate, 2),
            "current_week_tenants": current_week_tenants,
            "system_status": (
                "healthy"
                if critical_alerts == 0
                else "warning"
                if critical_alerts < CRITICAL_ALERT_THRESHOLD
                else "critical"
            ),
        }
        cache.set(cache_key, health_data, HEALTH_SUMMARY_CACHE_TTL_SECONDS)
    except (ImportError, models.ObjectDoesNotExist, TypeError):
        logger.exception("Erro ao obter resumo de saúde do sistema")
        health_data = {
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
    return health_data


@dataclass
class SystemAlertData:
    """Estrutura para dados de criação de alertas."""

    title: str
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    alert_type: str = "system"
    tenant: Tenant | None = None
    metadata: dict | None = None


def create_system_alert(alert_data: SystemAlertData) -> SystemAlert | None:
    """Cria um alerta do sistema.

    Args:
        alert_data: Objeto com os dados do alerta a ser criado.

    Returns:
        A instância do alerta criado ou None em caso de erro.

    """
    try:
        alert = SystemAlert.objects.create(
            title=alert_data.title,
            description=alert_data.description,
            severity=alert_data.severity,
            alert_type=alert_data.alert_type,
            tenant=alert_data.tenant,
            metadata=alert_data.metadata or {},
        )
        logger.warning(
            "Alerta criado: %s - Severidade: %s",
            alert_data.title,
            alert_data.severity,
        )
        if alert_data.severity == "critical":
            pass  # Lógica para notificações urgentes
    except (ValueError, TypeError):
        logger.exception("Erro ao criar alerta do sistema")
        alert = None
    return alert


def get_tenant_usage_stats(tenant: Tenant, days: int = 30) -> dict[str, Any]:
    """Retorna estatísticas de uso de um tenant específico.

    Args:
        tenant: Instância do Tenant.
        days: Número de dias para análise.

    Returns:
        Dicionário com estatísticas de uso.

    """
    try:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        metrics = TenantMetrics.objects.filter(
            tenant=tenant,
            date__range=[start_date, end_date],
        ).aggregate(
            avg_active_users=models.Avg("active_users"),
            max_active_users=models.Max("active_users"),
            total_storage_used=models.Sum("storage_used"),
            total_api_requests=models.Sum("api_requests"),
            avg_response_time=models.Avg("response_time_avg"),
            avg_uptime=models.Avg("uptime"),
            avg_error_rate=models.Avg("error_rate"),
        )

        mid_date = start_date + timedelta(days=days // 2)
        first_half = TenantMetrics.objects.filter(
            tenant=tenant,
            date__range=[start_date, mid_date],
        ).aggregate(avg_users=models.Avg("active_users"))
        second_half = TenantMetrics.objects.filter(
            tenant=tenant,
            date__range=[mid_date, end_date],
        ).aggregate(avg_users=models.Avg("active_users"))

        user_trend = 0
        avg_users_first = first_half.get("avg_users")
        avg_users_second = second_half.get("avg_users")
        if avg_users_first and avg_users_second:
            user_trend = ((avg_users_second - avg_users_first) / avg_users_first) * 100

        usage_data = {
            "period_days": days,
            "avg_active_users": round(metrics.get("avg_active_users") or 0, 1),
            "max_active_users": metrics.get("max_active_users") or 0,
            "total_storage_used_mb": round(
                (metrics.get("total_storage_used") or 0) / (1024 * 1024),
                2,
            ),
            "total_api_requests": metrics.get("total_api_requests") or 0,
            "avg_response_time": round(metrics.get("avg_response_time") or 0, 2),
            "avg_uptime": round(metrics.get("avg_uptime") or 100, 2),
            "avg_error_rate": round(metrics.get("avg_error_rate") or 0, 2),
            "user_trend_percent": round(user_trend, 2),
        }
    except (AttributeError, TypeError, ValueError):
        logger.exception("Erro ao obter estatísticas de uso do tenant %s", tenant)
        usage_data = {}
    return usage_data


@transaction.atomic
def cleanup_old_data(days_to_keep: int = 90) -> dict[str, int]:
    """Remove dados antigos para manter o banco de dados limpo.

    Args:
        days_to_keep: Número de dias de dados para manter.

    Returns:
        Dicionário com a contagem de registros removidos.

    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        metrics_count, _ = TenantMetrics.objects.filter(
            created_at__lt=cutoff_date,
        ).delete()
        activities_count, _ = (
            AdminActivity.objects.filter(
                created_at__lt=cutoff_date,
            )
            .exclude(action__in=["delete", "backup", "restore"])
            .delete()
        )
        alerts_count, _ = SystemAlert.objects.filter(
            created_at__lt=cutoff_date,
            status="resolved",
        ).delete()

        logger.info(
            "Limpeza concluída: %d métricas, %d atividades, %d alertas removidos",
            metrics_count,
            activities_count,
            alerts_count,
        )
        result = {
            "metrics_removed": metrics_count,
            "activities_removed": activities_count,
            "alerts_removed": alerts_count,
        }
    except (models.ProtectedError, ValueError):
        logger.exception("Erro durante limpeza de dados antigos")
        result = {}
    return result


def _validate_max_upload_size(value: float) -> tuple[bool, str]:
    if not isinstance(value, int | float) or value <= 0:
        return False, "Tamanho máximo de upload deve ser um número positivo"
    if value > MAX_UPLOAD_SIZE_BYTES:
        return False, f"Tamanho máximo de upload não pode exceder {MAX_UPLOAD_SIZE_MB}MB"
    return True, ""


def _validate_smtp_port(value: int) -> tuple[bool, str]:
    if not isinstance(value, int) or not (0 < value <= MAX_SMTP_PORT):
        return False, f"Porta SMTP deve ser um número entre 1 e {MAX_SMTP_PORT}"
    return True, ""


def _validate_backup_retention(value: int) -> tuple[bool, str]:
    if not isinstance(value, int) or not (1 <= value <= MAX_BACKUP_RETENTION_DAYS):
        return (
            False,
            f"Dias de retenção de backup deve ser entre 1 e {MAX_BACKUP_RETENTION_DAYS}",
        )
    return True, ""


def _validate_not_empty_string(
    value: str,
    max_len: int | None = None,
) -> tuple[bool, str]:
    if not isinstance(value, str) or not value.strip():
        return False, "O valor não pode estar vazio"
    if max_len and len(value) > max_len:
        return False, f"O valor não pode exceder {max_len} caracteres"
    return True, ""


def validate_system_configuration(key: str, value: str | float) -> tuple[bool, str]:
    """Valida configurações do sistema antes de salvar.

    Args:
        key: Chave da configuração.
        value: Valor a ser validado.

    Returns:
        Tupla (is_valid, error_message).

    """
    validators = {
        "max_upload_size": _validate_max_upload_size,
        "smtp_port": _validate_smtp_port,
        "backup_retention_days": _validate_backup_retention,
        "smtp_host": lambda v: _validate_not_empty_string(v),
        "site_name": lambda v: _validate_not_empty_string(v, MAX_SITE_NAME_LENGTH),
    }

    validator = validators.get(key)
    if validator:
        try:
            # A checagem de tipo é feita dentro de cada validador
            is_valid, message = validator(value)
        except (TypeError, ValueError):
            logger.exception("Erro ao validar configuração %s", key)
            return False, "Erro interno de validação"
        else:
            return is_valid, message

    return True, ""

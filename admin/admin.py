# admin/admin.py (Versão Corrigida)

from django.contrib import admin
from django.utils import timezone  # CORREÇÃO: Import adicionado

from .models import (
    AdminActivity,
    SystemAlert,
    SystemConfiguration,
    TenantBackup,
    TenantConfiguration,
    TenantMetrics,
    TenantUsageReport,
)


@admin.register(TenantMetrics)
class TenantMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "tenant",
        "date",
        "active_users",
        "total_users",
        "storage_used_mb",
        "api_requests",
        "uptime",
        "response_time_avg",
    ]
    list_filter = ["date", "tenant"]
    search_fields = ["tenant__name", "tenant__subdomain"]
    readonly_fields = ["created_at", "updated_at"]

    def storage_used_mb(self, obj):
        return f"{obj.storage_used / (1024 * 1024):.2f} MB"

    storage_used_mb.short_description = "Storage (MB)"


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ["title", "tenant", "severity", "status", "alert_type", "assigned_to", "created_at"]
    list_filter = ["severity", "status", "alert_type", "created_at"]
    search_fields = ["title", "description", "tenant__name"]
    readonly_fields = ["created_at", "updated_at", "acknowledged_at", "resolved_at"]
    actions = ["mark_as_acknowledged", "mark_as_resolved"]

    def mark_as_acknowledged(self, request, queryset):
        # CORREÇÃO: timezone.now() agora funciona devido ao import
        queryset.update(status="acknowledged", assigned_to=request.user, acknowledged_at=timezone.now())
        self.message_user(request, f"{queryset.count()} alertas marcados como reconhecidos.")

    mark_as_acknowledged.short_description = "Marcar como reconhecido"

    def mark_as_resolved(self, request, queryset):
        # CORREÇÃO: timezone.now() agora funciona devido ao import
        queryset.update(status="resolved", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} alertas marcados como resolvidos.")

    mark_as_resolved.short_description = "Marcar como resolvido"


@admin.register(TenantConfiguration)
class TenantConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        "tenant",
        "max_users",
        "max_storage_mb",
        "max_api_requests_per_hour",
        "backup_enabled",
        "require_2fa",
    ]
    list_filter = ["backup_enabled", "require_2fa"]
    search_fields = ["tenant__name", "tenant__subdomain"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AdminActivity)
class AdminActivityAdmin(admin.ModelAdmin):
    list_display = ["admin_user", "action", "resource_type", "resource_id", "tenant", "created_at", "ip_address"]
    list_filter = ["action", "resource_type", "created_at", "admin_user"]
    search_fields = ["admin_user__username", "description", "resource_type", "tenant__name"]
    readonly_fields = [f.name for f in AdminActivity._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TenantBackup)
class TenantBackupAdmin(admin.ModelAdmin):
    list_display = ["tenant", "backup_type", "status", "file_size_mb", "created_at", "completed_at", "duration_minutes"]
    list_filter = ["backup_type", "status", "created_at"]
    search_fields = ["tenant__name", "tenant__subdomain"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "checksum",
        "duration",
        "file_path",
        "error_message",
    ]

    def file_size_mb(self, obj):
        if obj.file_size:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
        return "-"

    file_size_mb.short_description = "Tamanho (MB)"

    def duration_minutes(self, obj):
        if obj.duration:
            return f"{obj.duration / 60:.1f} min"
        return "-"

    duration_minutes.short_description = "Duração (min)"


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ["key", "category", "is_public", "is_editable", "updated_at"]
    list_filter = ["category", "is_public", "is_editable"]
    search_fields = ["key", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TenantUsageReport)
class TenantUsageReportAdmin(admin.ModelAdmin):
    list_display = ["tenant", "report_type", "period_start", "period_end", "file_format", "is_generated", "created_at"]
    list_filter = ["report_type", "file_format", "is_generated", "created_at"]
    search_fields = ["tenant__name", "tenant__subdomain"]
    readonly_fields = ["created_at", "updated_at", "generated_at", "report_data", "summary", "file_path"]

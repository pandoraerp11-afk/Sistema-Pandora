from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AIAuditorSettings, AuditSession, CodeIssue, GeneratedTest


@admin.register(AuditSession)
class AuditSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "user",
        "status",
        "started_at",
        "completed_at",
        "total_issues",
        "critical_issues",
        "high_issues",
        "medium_issues",
        "low_issues",
    )
    list_filter = ("status", "tenant", "started_at")
    search_fields = ("tenant__name", "user__username", "error_message")
    date_hierarchy = "started_at"
    readonly_fields = (
        "started_at",
        "completed_at",
        "total_files_analyzed",
        "total_issues",
        "critical_issues",
        "high_issues",
        "medium_issues",
        "low_issues",
        "tests_generated",
        "fixes_applied",
    )
    fieldsets = (
        (None, {"fields": ("tenant", "user", "status", "error_message")}),
        (
            _("Detalhes da Análise"),
            {
                "fields": (
                    "started_at",
                    "completed_at",
                    "total_files_analyzed",
                    "total_issues",
                    "critical_issues",
                    "high_issues",
                    "medium_issues",
                    "low_issues",
                    "tests_generated",
                    "fixes_applied",
                    "analysis_config",
                )
            },
        ),
    )


@admin.register(CodeIssue)
class CodeIssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "app_name",
        "file_path",
        "line_number",
        "issue_type",
        "severity",
        "status",
        "title",
        "auto_fixable",
    )
    list_filter = ("issue_type", "severity", "status", "app_name", "session__tenant")
    search_fields = ("title", "description", "recommendation", "file_path")
    raw_id_fields = ("session", "fixed_by")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "fixed_at")
    fieldsets = (
        (None, {"fields": ("session", "app_name", "file_path", "line_number", "column_number")}),
        (
            _("Detalhes do Problema"),
            {
                "fields": (
                    "issue_type",
                    "severity",
                    "status",
                    "title",
                    "description",
                    "recommendation",
                    "code_snippet",
                    "suggested_fix",
                    "auto_fixable",
                )
            },
        ),
        (_("Resolução"), {"fields": ("fixed_at", "fixed_by")}),
    )


@admin.register(GeneratedTest)
class GeneratedTestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "app_name",
        "model_name",
        "test_type",
        "test_file_path",
        "is_applied",
        "applied_at",
    )
    list_filter = ("test_type", "app_name", "is_applied", "session__tenant")
    search_fields = ("app_name", "model_name", "test_file_path")
    raw_id_fields = ("session",)
    readonly_fields = ("created_at", "updated_at", "applied_at")
    fieldsets = (
        (None, {"fields": ("session", "app_name", "model_name", "test_type", "test_file_path")}),
        (_("Detalhes do Teste"), {"fields": ("test_code", "is_applied", "applied_at")}),
    )


@admin.register(AIAuditorSettings)
class AIAuditorSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "auto_fix_enabled",
        "auto_test_generation",
        "analysis_schedule",
        "email_notifications",
        "critical_threshold",
    )
    list_filter = ("auto_fix_enabled", "auto_test_generation", "email_notifications")
    search_fields = ("tenant__name",)
    raw_id_fields = ("tenant",)
    fieldsets = (
        (None, {"fields": ("tenant",)}),
        (
            _("Configurações de Automação"),
            {"fields": ("auto_fix_enabled", "auto_test_generation", "excluded_apps", "analysis_schedule")},
        ),
        (_("Configurações de Notificação"), {"fields": ("email_notifications", "critical_threshold")}),
    )

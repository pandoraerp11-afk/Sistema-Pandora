from django.contrib import admin

from .models import (
    ConfiguracaoNotificacao,
    EmailDelivery,
    LogNotificacao,
    Notification,
    NotificationAdvanced,
    NotificationMetrics,
    NotificationRecipient,
    NotificationRule,
    NotificationTemplate,
    PreferenciaUsuarioNotificacao,
    TenantNotificationSettings,
    UserNotificationPreferences,
)


class LogNotificacaoInline(admin.TabularInline):
    """Inline para logs de notificação"""

    model = LogNotificacao
    extra = 0
    readonly_fields = ["data_hora"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin para notificações"""

    list_display = ["id", "titulo", "tenant", "usuario_destinatario", "tipo", "prioridade", "status", "created_at"]
    list_filter = ["status", "tipo", "prioridade", "modulo_origem", "tenant", "created_at"]
    search_fields = ["titulo", "mensagem", "usuario_destinatario__username"]
    readonly_fields = ["created_at", "updated_at", "data_leitura"]
    inlines = [LogNotificacaoInline]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("tenant", "usuario_destinatario", "titulo", "mensagem", "tipo", "prioridade", "status")}),
        ("Datas", {"fields": ("created_at", "updated_at", "data_expiracao", "data_leitura")}),
        ("Referência", {"fields": ("content_type", "object_id", "url_acao")}),
        ("Metadados", {"fields": ("modulo_origem", "evento_origem", "dados_extras")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por tenant do usuário se não for superuser
        user_tenants = request.user.tenant_memberships.values_list("tenant", flat=True)
        return qs.filter(tenant__in=user_tenants)


@admin.register(LogNotificacao)
class LogNotificacaoAdmin(admin.ModelAdmin):
    """Admin para logs de notificação"""

    list_display = ["id", "notificacao", "usuario", "acao", "data_hora"]
    list_filter = ["data_hora", "notificacao__tenant"]
    search_fields = ["notificacao__titulo", "usuario__username", "acao"]
    readonly_fields = ["data_hora"]
    date_hierarchy = "data_hora"


@admin.register(ConfiguracaoNotificacao)
class ConfiguracaoNotificacaoAdmin(admin.ModelAdmin):
    """Admin para configurações de notificação por tenant"""

    list_display = [
        "id",
        "tenant",
        "dias_expiracao_padrao",
        "max_notificacoes_por_hora",
        "agrupar_notificacoes_similares",
    ]
    list_filter = ["agrupar_notificacoes_similares", "email_habilitado", "push_habilitado", "sms_habilitado"]
    search_fields = ["tenant__name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("tenant",)}),
        (
            "Configurações de Expiração",
            {"fields": ("dias_expiracao_padrao", "dias_retencao_lidas", "dias_retencao_arquivadas")},
        ),
        ("Configurações de Envio", {"fields": ("max_notificacoes_por_hora", "agrupar_notificacoes_similares")}),
        ("Canais", {"fields": ("email_habilitado", "push_habilitado", "sms_habilitado")}),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(PreferenciaUsuarioNotificacao)
class PreferenciaUsuarioNotificacaoAdmin(admin.ModelAdmin):
    """Admin para preferências de notificação por usuário"""

    list_display = ["id", "usuario", "receber_notificacoes", "email_habilitado", "push_habilitado", "sms_habilitado"]
    list_filter = ["receber_notificacoes", "email_habilitado", "push_habilitado", "sms_habilitado"]
    search_fields = ["usuario__username", "usuario__email"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("usuario", "receber_notificacoes")}),
        (
            "Preferências por Tipo",
            {"fields": ("receber_info", "receber_warning", "receber_error", "receber_success", "receber_alert")},
        ),
        (
            "Preferências por Prioridade",
            {"fields": ("receber_baixa", "receber_media", "receber_alta", "receber_critica")},
        ),
        ("Módulos", {"fields": ("modulos_bloqueados",)}),
        ("Canais", {"fields": ("email_habilitado", "push_habilitado", "sms_habilitado")}),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )


# ================== Admin modelos avançados ==================


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "inapp_title", "email_subject"]
    search_fields = ["name", "inapp_title", "email_subject"]
    list_filter = ["created_at"]


@admin.register(NotificationAdvanced)
class NotificationAdvancedAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "tenant", "priority", "status", "source_module", "created_at"]
    search_fields = ["title", "content", "source_module"]
    list_filter = ["priority", "status", "source_module", "tenant"]
    date_hierarchy = "created_at"


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ["id", "notification", "user", "email_sent", "push_sent", "inapp_sent", "sent_date"]
    search_fields = ["notification__title", "user__username", "user__email"]
    list_filter = ["email_sent", "push_sent", "inapp_sent", "sent_date"]


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "tenant", "source_module", "event_type", "active", "priority"]
    search_fields = ["name", "event_type", "source_module"]
    list_filter = ["active", "source_module", "priority", "tenant"]


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ["id", "notification_recipient", "email_address", "delivery_status", "provider"]
    list_filter = ["delivery_status", "provider"]
    search_fields = ["email_address", "notification_recipient__notification__title"]


@admin.register(NotificationMetrics)
class NotificationMetricsAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "date", "hour", "notifications_created", "notifications_sent"]
    list_filter = ["tenant", "date", "hour"]
    search_fields = ["tenant__name"]


@admin.register(TenantNotificationSettings)
class TenantNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "max_notifications_per_hour", "max_notifications_per_day", "default_email_enabled"]
    search_fields = ["tenant__name"]


@admin.register(UserNotificationPreferences)
class UserNotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "enabled", "email_enabled", "push_enabled", "quiet_hours_enabled"]
    search_fields = ["user__username", "user__email"]

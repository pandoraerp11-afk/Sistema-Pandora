from django.contrib import admin

from .models import ConfiguracaoChat, Conversa, LogMensagem, Mensagem, ParticipanteConversa, PreferenciaUsuarioChat


class ParticipanteConversaInline(admin.TabularInline):
    """Inline para participantes de conversa"""

    model = ParticipanteConversa
    extra = 0
    readonly_fields = ["created_at", "updated_at", "data_entrada", "data_saida"]


class MensagemInline(admin.TabularInline):
    """Inline para mensagens da conversa"""

    model = Mensagem
    extra = 0
    readonly_fields = ["created_at", "updated_at", "data_leitura", "data_edicao"]
    fields = ["remetente", "conteudo", "tipo", "status", "lida"]


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    """Admin para conversas"""

    list_display = ["id", "get_titulo_display", "tenant", "tipo", "status", "criador", "ultima_atividade"]
    list_filter = ["tipo", "status", "tenant", "created_at"]
    search_fields = ["titulo", "criador__username"]
    readonly_fields = ["created_at", "updated_at", "uuid", "ultima_atividade"]
    inlines = [ParticipanteConversaInline, MensagemInline]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("tenant", "titulo", "tipo", "status", "criador")}),
        ("Metadados", {"fields": ("uuid", "created_at", "updated_at", "ultima_atividade")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por tenant do usuário se não for superuser
        user_tenants = request.user.tenant_memberships.values_list("tenant", flat=True)
        return qs.filter(tenant__in=user_tenants)


@admin.register(ParticipanteConversa)
class ParticipanteConversaAdmin(admin.ModelAdmin):
    """Admin para participantes de conversa"""

    list_display = ["id", "conversa", "usuario", "ativo", "data_entrada", "data_saida", "notificacoes_habilitadas"]
    list_filter = ["ativo", "notificacoes_habilitadas", "data_entrada", "conversa__tenant"]
    search_fields = ["usuario__username", "conversa__titulo"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "data_entrada"


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    """Admin para mensagens"""

    list_display = ["id", "conversa", "remetente", "tipo", "status", "lida", "created_at"]
    list_filter = ["tipo", "status", "lida", "tenant", "created_at"]
    search_fields = ["conteudo", "remetente__username", "conversa__titulo"]
    readonly_fields = ["created_at", "updated_at", "uuid", "data_leitura", "data_edicao"]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("tenant", "conversa", "remetente", "conteudo", "tipo", "status")}),
        ("Arquivo", {"fields": ("arquivo", "nome_arquivo_original")}),
        ("Status", {"fields": ("lida", "data_leitura", "data_edicao")}),
        ("Resposta", {"fields": ("resposta_para",)}),
        ("Metadados", {"fields": ("uuid", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por tenant do usuário se não for superuser
        user_tenants = request.user.tenant_memberships.values_list("tenant", flat=True)
        return qs.filter(tenant__in=user_tenants)


@admin.register(LogMensagem)
class LogMensagemAdmin(admin.ModelAdmin):
    """Admin para logs de mensagem"""

    list_display = ["id", "mensagem", "usuario", "acao", "data_hora"]
    list_filter = ["data_hora", "mensagem__tenant"]
    search_fields = ["mensagem__conteudo", "usuario__username", "acao"]
    readonly_fields = ["data_hora"]
    date_hierarchy = "data_hora"


@admin.register(ConfiguracaoChat)
class ConfiguracaoChatAdmin(admin.ModelAdmin):
    """Admin para configurações do chat por tenant"""

    list_display = [
        "id",
        "tenant",
        "tamanho_maximo_arquivo_mb",
        "moderacao_habilitada",
        "notificacoes_push_habilitadas",
    ]
    list_filter = ["moderacao_habilitada", "notificacoes_push_habilitadas", "notificacoes_email_habilitadas"]
    search_fields = ["tenant__name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("tenant",)}),
        ("Configurações de Arquivo", {"fields": ("tamanho_maximo_arquivo_mb", "tipos_arquivo_permitidos")}),
        ("Configurações de Retenção", {"fields": ("dias_retencao_mensagens",)}),
        ("Configurações de Moderação", {"fields": ("moderacao_habilitada", "palavras_bloqueadas")}),
        (
            "Configurações de Notificação",
            {"fields": ("notificacoes_push_habilitadas", "notificacoes_email_habilitadas")},
        ),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(PreferenciaUsuarioChat)
class PreferenciaUsuarioChatAdmin(admin.ModelAdmin):
    """Admin para preferências de chat por usuário"""

    list_display = ["id", "usuario", "notificacoes_habilitadas", "status_online_visivel", "tema_escuro"]
    list_filter = ["notificacoes_habilitadas", "som_notificacao_habilitado", "status_online_visivel", "tema_escuro"]
    search_fields = ["usuario__username", "usuario__email"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("usuario",)}),
        ("Configurações de Notificação", {"fields": ("notificacoes_habilitadas", "som_notificacao_habilitado")}),
        ("Configurações de Privacidade", {"fields": ("status_online_visivel", "ultima_visualizacao_visivel")}),
        ("Configurações de Interface", {"fields": ("tema_escuro", "tamanho_fonte")}),
        ("Datas", {"fields": ("created_at", "updated_at")}),
    )

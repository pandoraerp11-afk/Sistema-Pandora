from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ConviteUsuario, LogAtividadeUsuario, PerfilUsuarioEstendido, PermissaoPersonalizada, SessaoUsuario

User = get_user_model()


class PerfilUsuarioEstendidoInline(admin.StackedInline):
    model = PerfilUsuarioEstendido
    can_delete = False
    verbose_name_plural = "Perfil Estendido"
    fk_name = "user"
    fieldsets = (
        ("Informações Básicas", {"fields": ("tipo_usuario", "status")}),
        ("Informações Pessoais", {"fields": ("cpf", "rg", "data_nascimento", "telefone", "celular")}),
        ("Endereço", {"fields": ("endereco", "numero", "complemento", "bairro", "cidade", "estado", "cep")}),
        ("Informações Profissionais", {"fields": ("cargo", "departamento", "data_admissao", "salario")}),
        (
            "Configurações de Segurança",
            {"fields": ("autenticacao_dois_fatores", "ultimo_login_ip", "tentativas_login_falhadas", "bloqueado_ate")},
        ),
        (
            "Configurações de Notificação",
            {"fields": ("receber_email_notificacoes", "receber_sms_notificacoes", "receber_push_notificacoes")},
        ),
    )


class CustomUserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioEstendidoInline,)
    list_display = ("username", "email", "first_name", "last_name", "get_tipo_usuario", "get_status", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("perfil_estendido__tipo_usuario", "perfil_estendido__status")

    def get_tipo_usuario(self, obj):
        if hasattr(obj, "perfil_estendido"):
            return obj.perfil_estendido.get_tipo_usuario_display()
        return "-"

    get_tipo_usuario.short_description = "Tipo de Usuário"

    def get_status(self, obj):
        if hasattr(obj, "perfil_estendido"):
            return obj.perfil_estendido.get_status_display()
        return "-"

    get_status.short_description = "Status"


@admin.register(PerfilUsuarioEstendido)
class PerfilUsuarioEstendidoAdmin(admin.ModelAdmin):
    list_display = ("user", "tipo_usuario", "status", "cargo", "departamento", "criado_em")
    list_filter = ("tipo_usuario", "status", "departamento", "criado_em")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "cpf", "cargo")
    readonly_fields = ("criado_em", "atualizado_em", "ultimo_login_ip", "tentativas_login_falhadas")
    actions = ["resetar_2fa"]

    fieldsets = (
        ("Usuário", {"fields": ("user", "tipo_usuario", "status")}),
        ("Informações Pessoais", {"fields": ("cpf", "rg", "data_nascimento", "telefone", "celular")}),
        ("Endereço", {"fields": ("endereco", "numero", "complemento", "bairro", "cidade", "estado", "cep")}),
        ("Informações Profissionais", {"fields": ("cargo", "departamento", "data_admissao", "salario")}),
        (
            "Configurações de Segurança",
            {"fields": ("autenticacao_dois_fatores", "ultimo_login_ip", "tentativas_login_falhadas", "bloqueado_ate")},
        ),
        (
            "Configurações de Notificação",
            {"fields": ("receber_email_notificacoes", "receber_sms_notificacoes", "receber_push_notificacoes")},
        ),
        ("Metadados", {"fields": ("criado_em", "atualizado_em", "criado_por")}),
    )

    def resetar_2fa(self, request, queryset):
        from .twofa import disable_2fa

        count = 0
        for perfil in queryset:
            if perfil.autenticacao_dois_fatores or perfil.totp_secret:
                disable_2fa(perfil)
                count += 1
        self.message_user(request, f"2FA resetado para {count} usuário(s).")

    resetar_2fa.short_description = "Resetar 2FA selecionados"


@admin.register(ConviteUsuario)
class ConviteUsuarioAdmin(admin.ModelAdmin):
    list_display = ("email", "tipo_usuario", "enviado_por", "enviado_em", "usado", "esta_expirado")
    list_filter = ("tipo_usuario", "usado", "enviado_em")
    search_fields = ("email", "nome_completo", "enviado_por__username")
    readonly_fields = ("token", "enviado_em", "aceito_em", "esta_expirado", "pode_ser_usado")

    fieldsets = (
        ("Informações do Convite", {"fields": ("email", "tipo_usuario", "nome_completo", "cargo", "departamento")}),
        ("Mensagem", {"fields": ("mensagem_personalizada",)}),
        (
            "Status",
            {"fields": ("token", "enviado_em", "aceito_em", "expirado_em", "usado", "esta_expirado", "pode_ser_usado")},
        ),
        ("Relacionamentos", {"fields": ("enviado_por", "usuario_criado")}),
    )


@admin.register(SessaoUsuario)
class SessaoUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "criada_em", "ultima_atividade", "ativa")
    list_filter = ("ativa", "criada_em", "ultima_atividade")
    search_fields = ("user__username", "ip_address", "user_agent")
    readonly_fields = ("session_key", "criada_em", "ultima_atividade")

    fieldsets = (
        ("Informações da Sessão", {"fields": ("user", "session_key", "ip_address", "user_agent", "ativa")}),
        ("Timestamps", {"fields": ("criada_em", "ultima_atividade")}),
        ("Localização", {"fields": ("pais", "cidade")}),
    )


@admin.register(LogAtividadeUsuario)
class LogAtividadeUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "acao", "modulo", "timestamp", "ip_address")
    list_filter = ("acao", "modulo", "timestamp")
    search_fields = ("user__username", "acao", "descricao", "ip_address")
    readonly_fields = ("timestamp",)
    date_hierarchy = "timestamp"

    fieldsets = (
        ("Informações da Atividade", {"fields": ("user", "acao", "descricao", "modulo")}),
        ("Objeto Relacionado", {"fields": ("objeto_id", "objeto_tipo")}),
        ("Informações Técnicas", {"fields": ("ip_address", "user_agent", "timestamp")}),
    )


@admin.register(PermissaoPersonalizada)
class PermissaoPersonalizadaAdmin(admin.ModelAdmin):
    list_display = ("user", "modulo", "acao", "recurso", "concedida", "esta_ativa", "data_concessao")
    list_filter = ("modulo", "acao", "concedida", "data_concessao")
    search_fields = ("user__username", "modulo", "acao", "recurso")
    readonly_fields = ("data_concessao", "esta_ativa")

    fieldsets = (
        ("Permissão", {"fields": ("user", "modulo", "acao", "recurso", "concedida")}),
        ("Validade", {"fields": ("data_concessao", "data_expiracao", "esta_ativa")}),
        ("Metadados", {"fields": ("concedida_por", "observacoes")}),
    )


# Desregistrar o UserAdmin padrão e registrar o customizado
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

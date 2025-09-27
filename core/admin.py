"""Admin do app core.

Inclui configurações avançadas e inlines para administração multi-tenant,
mantendo compatibilidade com o legado e atendendo padrões de lint/typing.
"""

from typing import ClassVar

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    AuditLog,
    Certificacao,
    ConfiguracaoSistema,
    Contato,
    CustomUser,
    DadosBancarios,
    Department,
    EmpresaDocumento,
    EmpresaDocumentoVersao,
    Endereco,
    Modulo,
    Role,
    Tenant,
    TenantDocumento,
    TenantPessoaFisica,
    TenantPessoaJuridica,
    TenantUser,
    UserProfile,
)

# ============================================================================
# INLINES PARA MODELOS RELACIONADOS
# ============================================================================


class EnderecoInline(admin.TabularInline):
    """Inline para endereços do tenant."""

    model = Endereco
    extra = 1
    verbose_name = _("Endereço")
    verbose_name_plural = _("Endereços")
    fields = (
        "tipo",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cidade",
        "uf",
        "cep",
        "pais",
        "ponto_referencia",
    )


class ContatoInline(admin.TabularInline):
    """Inline para contatos do tenant."""

    model = Contato
    extra = 1
    verbose_name = _("Contato")
    verbose_name_plural = _("Contatos")
    fields = ("nome", "email", "telefone", "cargo")


class TenantDocumentoInline(admin.TabularInline):
    """Inline para documentos anexados ao tenant."""

    model = TenantDocumento
    extra = 1
    verbose_name = _("Documento da Empresa")
    verbose_name_plural = _("Documentos da Empresa")
    fields = ("descricao", "arquivo")


class CertificacaoInline(admin.TabularInline):
    """Inline para certificações do tenant."""

    model = Certificacao
    extra = 1
    verbose_name = _("Certificação")
    verbose_name_plural = _("Certificações")
    fields = (
        "nome_certificacao",
        "entidade_emissora",
        "data_emissao",
        "data_validade",
        "numero_registro",
        "arquivo_anexo",
        "observacoes",
    )


class DadosBancariosInline(admin.TabularInline):
    """Inline para dados bancários do tenant."""

    model = DadosBancarios
    extra = 1
    verbose_name = _("Dado Bancário")
    verbose_name_plural = _("Dados Bancários")
    fields = ("banco", "agencia", "conta", "digito", "tipo_conta", "chave_pix", "observacoes")


class TenantPessoaFisicaInline(admin.StackedInline):
    """Inline com informações específicas de pessoa física (PF)."""

    model = TenantPessoaFisica
    can_delete = False
    verbose_name = _("Informações de Pessoa Física")
    verbose_name_plural = _("Informações de Pessoa Física")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nome_completo",
                    "cpf",
                    "rg",
                    "data_nascimento",
                    "sexo",
                    "naturalidade",
                    "nacionalidade",
                    "profissao",
                    "estado_civil",
                    "nome_mae",
                    "nome_pai",
                ),
            },
        ),
    )


class TenantPessoaJuridicaInline(admin.StackedInline):
    """Inline com informações específicas de pessoa jurídica (PJ)."""

    model = TenantPessoaJuridica
    can_delete = False
    verbose_name = _("Informações de Pessoa Jurídica")
    verbose_name_plural = _("Informações de Pessoa Jurídica")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "razao_social",
                    "nome_fantasia",
                    "cnpj",
                    "inscricao_estadual",
                    "inscricao_municipal",
                    "data_fundacao",
                    "ramo_atividade",
                    "porte_empresa",
                    "website",
                    "email_financeiro",
                    "telefone_financeiro",
                ),
            },
        ),
    )


class ConfiguracaoSistemaInline(admin.StackedInline):
    """Inline com configurações de sistema por tenant."""

    model = ConfiguracaoSistema
    can_delete = False
    verbose_name = _("Configurações do Sistema")
    verbose_name_plural = _("Configurações do Sistema")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "permitir_cadastro_auto_clientes",
                    "limite_documentos_upload",
                    "notificacoes_email_ativas",
                    "cor_primaria_sistema",
                    "logo_login",
                    "termos_uso",
                    "politica_privacidade",
                ),
            },
        ),
    )


class EmpresaDocumentoVersaoInline(admin.TabularInline):
    """Inline para versões de documentos da empresa."""

    model = EmpresaDocumentoVersao
    extra = 0
    fields = (
        "versao",
        "arquivo",
        "data_vigencia_inicio",
        "data_vigencia_fim",
        "competencia",
        "observacao",
        "usuario",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-data_vigencia_inicio", "-versao")


# ============================================================================
# ADMIN PARA O MODELO TENANT
# ============================================================================


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin do modelo `Tenant` com inlines e filtros personalizados."""

    list_display = (
        "name",
        "subdomain",
        "display_status",
        "tipo_pessoa",
        "email",
        "telefone",
        "data_ativacao_plano",
        "portal_ativo",
    )
    list_filter = (
        "status",
        "tipo_pessoa",
        "plano_assinatura",
        "portal_ativo",
        "regime_tributario",
        "timezone",
        "idioma_padrao",
        "moeda_padrao",
    )
    search_fields = ("name", "subdomain", "cnpj", "cpf", "email", "telefone", "razao_social", "nome_contato_principal")
    readonly_fields = ("created_at", "updated_at")
    inlines: ClassVar[tuple[type[InlineModelAdmin], ...]] = (
        EnderecoInline,
        ContatoInline,
        TenantDocumentoInline,
        CertificacaoInline,
        DadosBancariosInline,
        ConfiguracaoSistemaInline,
    )

    fieldsets = (
        (
            None,
            {
                "fields": ("name", "subdomain", "status", "logo", "observacoes", "created_at", "updated_at"),
            },
        ),
        (
            _("Informações de Identificação"),
            {
                "fields": ("tipo_pessoa", "codigo_interno", "nome_contato_principal"),
                "description": _("Informações básicas para identificação da empresa/pessoa."),
            },
        ),
        (
            _("Dados de Contato"),
            {
                "fields": (
                    "email",
                    "email_financeiro",
                    "email_comercial",
                    "email_tecnico",
                    "telefone",
                    "telefone_secundario",
                    "telefone_financeiro",
                    "telefone_comercial",
                    "telefone_emergencia",
                    "whatsapp",
                ),
                "description": _("Canais de comunicação da empresa."),
            },
        ),
        (
            _("Dados Fiscais e Tributários"),
            {
                "fields": (
                    "razao_social",
                    "cnpj",
                    "inscricao_estadual",
                    "inscricao_municipal",
                    "regime_tributario",
                    "inscricao_suframa",
                ),
                "description": _("Informações relevantes para questões fiscais e tributárias."),
            },
        ),
        (
            _("Informações de Pessoa Jurídica (PJ)"),
            {
                "fields": (
                    "data_fundacao",
                    "data_abertura",
                    "porte_empresa",
                    "ramo_atividade",
                    "cnae_principal",
                    "cnae_secundarios",
                    "website",
                    "redes_sociais",
                    "nome_responsavel_financeiro",
                    "nome_responsavel_comercial",
                    "nome_responsavel_tecnico",
                ),
                "description": _("Campos específicos para empresas (Pessoa Jurídica)."),
            },
        ),
        (
            _("Informações de Pessoa Física (PF)"),
            {
                "fields": (
                    "cpf",
                    "rg",
                    "data_nascimento",
                    "sexo",
                    "naturalidade",
                    "nacionalidade",
                    "nome_mae",
                    "nome_pai",
                    "estado_civil",
                    "profissao",
                ),
                "description": _("Campos específicos para pessoas físicas."),
            },
        ),
        (
            _("Dados Específicos por Setor"),
            {
                "fields": ("dados_construcao_civil", "dados_saude", "dados_comerciais", "dados_servicos"),
                "description": _("Campos JSON para dados específicos de cada setor de atuação."),
            },
        ),
        (
            _("Configurações Operacionais e de Assinatura"),
            {
                "fields": (
                    "timezone",
                    "idioma_padrao",
                    "moeda_padrao",
                    "formato_data",
                    "plano_assinatura",
                    "data_ativacao_plano",
                    "data_proxima_cobranca",
                    "data_fim_trial",
                    "max_usuarios",
                    "max_armazenamento_gb",
                    "portal_ativo",
                    "enabled_modules",
                ),
                "description": _("Configurações de sistema e detalhes do plano de assinatura."),
            },
        ),
    )

    def get_inlines(self, request: HttpRequest, obj: Tenant | None = None) -> list[type[InlineModelAdmin]]:
        """Retorna inlines de acordo com o tipo de pessoa do tenant."""
        inlines: list[type[InlineModelAdmin]] = list(super().get_inlines(request, obj))
        if obj and obj.tipo_pessoa == "PF":
            inlines = [TenantPessoaFisicaInline] + [i for i in inlines if i not in [TenantPessoaJuridicaInline]]
        elif obj and obj.tipo_pessoa == "PJ":
            inlines = [TenantPessoaJuridicaInline] + [i for i in inlines if i not in [TenantPessoaFisicaInline]]
        else:
            inlines = [i for i in inlines if i not in [TenantPessoaFisicaInline, TenantPessoaJuridicaInline]]
        return inlines

    @admin.display(description=_("Status"), ordering="status")
    def display_status(self, obj: Tenant) -> str:
        """Exibe o status com cor no admin."""
        colors = {
            "active": "green",
            "inactive": "red",
            "suspended": "orange",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )


# ============================================================================
# ADMINS PARA OUTROS MODELOS DO CORE
# ============================================================================


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    """Admin para endereços."""

    list_display = ("tenant", "tipo", "logradouro", "numero", "cidade", "uf", "cep")
    list_filter = ("tipo", "uf", "pais", "tenant")
    search_fields = ("logradouro", "numero", "bairro", "cidade", "cep", "tenant__name")


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    """Admin para contatos."""

    list_display = ("tenant", "nome", "email", "telefone", "cargo")
    list_filter = ("cargo", "tenant")
    search_fields = ("nome", "email", "telefone", "tenant__name")


@admin.register(TenantDocumento)
class TenantDocumentoAdmin(admin.ModelAdmin):
    """Admin para documentos do tenant."""

    list_display = ("tenant", "descricao", "arquivo", "created_at")
    list_filter = ("tenant",)
    search_fields = ("descricao", "tenant__name")


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """Admin para usuários customizados."""

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
        "last_login",
    )
    list_filter = ("is_staff", "is_active", "is_superuser", "groups")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Informações Pessoais"), {"fields": ("first_name", "last_name", "email", "profile_image", "phone", "bio")}),
        (_("Permissões"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (
            _("Datas Importantes"),
            {"fields": ("last_login", "date_joined", "last_password_change", "require_password_change")},
        ),
        (_("Segurança"), {"fields": ("is_active_directory_user", "login_attempts", "is_locked")}),
        (_("Preferências"), {"fields": ("theme_preference",)}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin para perfis de usuário."""

    list_display = (
        "user",
        "email_notifications",
        "sms_notifications",
        "push_notifications",
        "items_per_page",
        "language",
        "timezone",
    )
    list_filter = ("email_notifications", "sms_notifications", "push_notifications", "language", "timezone")
    search_fields = ("user__username", "user__email")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin para papéis (roles)."""

    list_display = ("tenant", "name", "description")
    list_filter = ("tenant",)
    search_fields = ("name", "description", "tenant__name")
    filter_horizontal = ("permissions",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin para departamentos."""

    list_display = ("tenant", "name", "description")
    list_filter = ("tenant",)
    search_fields = ("name", "description", "tenant__name")


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    """Admin para relacionamento Tenant-Usuário."""

    list_display = ("tenant", "user", "role", "department", "is_tenant_admin")
    list_filter = ("tenant", "role", "department", "is_tenant_admin")
    search_fields = ("tenant__name", "user__username", "role__name", "department__name")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin para registros de auditoria."""

    list_display = ("action_time", "user", "tenant", "action_type", "content_object", "ip_address")
    list_filter = ("action_type", "tenant", "user", "content_type")
    search_fields = ("user__username", "tenant__name", "change_message", "ip_address")
    readonly_fields = (
        "action_time",
        "user",
        "tenant",
        "action_type",
        "change_message",
        "ip_address",
        "content_type",
        "object_id",
        "content_object",
    )


@admin.register(Certificacao)
class CertificacaoAdmin(admin.ModelAdmin):
    """Admin para certificações."""

    list_display = (
        "tenant",
        "nome_certificacao",
        "entidade_emissora",
        "data_emissao",
        "data_validade",
        "is_valid",
        "days_to_expire",
    )
    list_filter = ("tenant", "entidade_emissora", "data_validade")
    search_fields = ("nome_certificacao", "entidade_emissora", "numero_registro", "tenant__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DadosBancarios)
class DadosBancariosAdmin(admin.ModelAdmin):
    """Admin para dados bancários."""

    list_display = ("tenant", "banco", "agencia", "conta", "tipo_conta", "chave_pix")
    list_filter = ("tenant", "banco", "tipo_conta")
    search_fields = ("banco", "agencia", "conta", "chave_pix", "tenant__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    """Admin para configurações do sistema por tenant."""

    list_display = ("tenant", "permitir_cadastro_auto_clientes", "notificacoes_email_ativas", "cor_primaria_sistema")
    list_filter = ("permitir_cadastro_auto_clientes", "notificacoes_email_ativas")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    """Admin para módulos do sistema."""

    list_display = ("nome", "descricao", "ativo_por_padrao")
    list_filter = ("ativo_por_padrao",)
    search_fields = ("nome", "descricao")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmpresaDocumento)
class EmpresaDocumentoAdmin(admin.ModelAdmin):
    """Admin para tipos de documentos da empresa."""

    list_display = ("tenant", "tipo", "status_atual", "versao_atual", "versionavel", "periodicidade")
    list_filter = ("tenant", "status_atual", "tipo__categoria", "tipo__periodicidade")
    search_fields = ("tenant__name", "tipo__nome")
    inlines: ClassVar[tuple[type[InlineModelAdmin], ...]] = (EmpresaDocumentoVersaoInline,)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(boolean=True, description=_("Versionável"))
    def versionavel(self, obj: EmpresaDocumento) -> bool:
        """Indica se o tipo associado é versionável."""
        return bool(getattr(getattr(obj, "tipo", None), "versionavel", False))

    @admin.display(description=_("Periodicidade"))
    def periodicidade(self, obj: EmpresaDocumento) -> str:
        """Retorna a periodicidade legível do tipo, se houver."""
        tipo = getattr(obj, "tipo", None)
        getter = getattr(tipo, "get_periodicidade_display", None)
        value = getter() if callable(getter) else "-"
        return str(value)

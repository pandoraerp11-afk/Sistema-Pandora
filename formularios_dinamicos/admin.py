from django.contrib import admin

from .models import (
    ArquivoResposta,
    CampoFormulario,
    CondicaoFormulario,
    FormularioDinamico,
    LogFormulario,
    RespostaFormulario,
    TemplateFormulario,
)


class CampoFormularioInline(admin.TabularInline):
    model = CampoFormulario
    extra = 0
    fields = ["nome", "label", "tipo", "obrigatorio", "ordem"]
    ordering = ["ordem"]


class CondicaoFormularioInline(admin.TabularInline):
    model = CondicaoFormulario
    extra = 0
    fk_name = "formulario"


@admin.register(FormularioDinamico)
class FormularioDinamicoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "status", "publico", "total_campos", "total_respostas", "criado_por", "criado_em"]
    list_filter = ["status", "publico", "requer_login", "criado_em"]
    search_fields = ["titulo", "descricao", "slug"]
    prepopulated_fields = {"slug": ("titulo",)}
    readonly_fields = ["criado_em", "atualizado_em", "total_campos", "total_respostas"]
    inlines = [CampoFormularioInline, CondicaoFormularioInline]

    fieldsets = (
        ("Informações Básicas", {"fields": ("titulo", "slug", "descricao", "status")}),
        ("Configurações de Acesso", {"fields": ("publico", "requer_login", "permite_multiplas_respostas")}),
        ("Período de Atividade", {"fields": ("data_inicio", "data_fim")}),
        ("Notificações", {"fields": ("notificar_nova_resposta", "emails_notificacao")}),
        ("Aparência", {"fields": ("cor_tema", "css_personalizado")}),
        ("Configurações Avançadas", {"fields": ("configuracoes_avancadas",), "classes": ("collapse",)}),
        (
            "Metadados",
            {
                "fields": ("criado_por", "criado_em", "atualizado_em", "total_campos", "total_respostas"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(CampoFormulario)
class CampoFormularioAdmin(admin.ModelAdmin):
    list_display = ["formulario", "label", "tipo", "obrigatorio", "ordem"]
    list_filter = ["tipo", "obrigatorio", "formulario"]
    search_fields = ["nome", "label", "formulario__titulo"]
    ordering = ["formulario", "ordem"]

    fieldsets = (
        ("Informações Básicas", {"fields": ("formulario", "nome", "label", "tipo")}),
        ("Configurações", {"fields": ("obrigatorio", "placeholder", "help_text", "valor_padrao")}),
        ("Validações", {"fields": ("min_length", "max_length", "min_value", "max_value", "regex_validacao")}),
        ("Opções (para campos de seleção)", {"fields": ("opcoes",)}),
        ("Aparência e Layout", {"fields": ("css_classes", "largura_coluna", "ordem", "grupo")}),
        ("Configurações Avançadas", {"fields": ("configuracoes_avancadas",), "classes": ("collapse",)}),
    )


class ArquivoRespostaInline(admin.TabularInline):
    model = ArquivoResposta
    extra = 0
    readonly_fields = ["nome_original", "tamanho", "tipo_mime", "criado_em"]


@admin.register(RespostaFormulario)
class RespostaFormularioAdmin(admin.ModelAdmin):
    list_display = ["formulario", "usuario_display", "status", "criado_em", "enviado_em"]
    list_filter = ["status", "formulario", "criado_em"]
    search_fields = ["formulario__titulo", "usuario__username", "usuario__email"]
    readonly_fields = ["token", "criado_em", "atualizado_em", "ip_address", "user_agent"]
    inlines = [ArquivoRespostaInline]

    fieldsets = (
        ("Informações Básicas", {"fields": ("formulario", "usuario", "status", "token")}),
        ("Dados da Resposta", {"fields": ("dados",)}),
        (
            "Informações de Submissão",
            {"fields": ("ip_address", "user_agent", "criado_em", "atualizado_em", "enviado_em")},
        ),
        ("Análise", {"fields": ("analisado_por", "analisado_em", "observacoes_analise")}),
    )

    def usuario_display(self, obj):
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return "Anônimo"

    usuario_display.short_description = "Usuário"


@admin.register(ArquivoResposta)
class ArquivoRespostaAdmin(admin.ModelAdmin):
    list_display = ["resposta", "campo", "nome_original", "tamanho_formatado", "criado_em"]
    list_filter = ["tipo_mime", "criado_em"]
    search_fields = ["nome_original", "resposta__formulario__titulo"]
    readonly_fields = ["tamanho", "tipo_mime", "criado_em"]

    def tamanho_formatado(self, obj):
        if obj.tamanho < 1024:
            return f"{obj.tamanho} bytes"
        elif obj.tamanho < 1024 * 1024:
            return f"{obj.tamanho / 1024:.1f} KB"
        else:
            return f"{obj.tamanho / (1024 * 1024):.1f} MB"

    tamanho_formatado.short_description = "Tamanho"


@admin.register(LogFormulario)
class LogFormularioAdmin(admin.ModelAdmin):
    list_display = ["formulario", "acao", "usuario", "timestamp"]
    list_filter = ["acao", "timestamp"]
    search_fields = ["formulario__titulo", "acao", "descricao"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"

    fieldsets = (
        ("Informações da Ação", {"fields": ("formulario", "usuario", "acao", "descricao")}),
        ("Dados", {"fields": ("dados_anteriores", "dados_novos")}),
        ("Informações Técnicas", {"fields": ("ip_address", "user_agent", "timestamp")}),
    )


@admin.register(TemplateFormulario)
class TemplateFormularioAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "ativo", "publico", "criado_por", "criado_em"]
    list_filter = ["categoria", "ativo", "publico", "criado_em"]
    search_fields = ["nome", "descricao", "categoria"]
    readonly_fields = ["criado_em"]

    fieldsets = (
        ("Informações Básicas", {"fields": ("nome", "categoria", "descricao")}),
        ("Configuração", {"fields": ("configuracao",)}),
        ("Status", {"fields": ("ativo", "publico")}),
        ("Metadados", {"fields": ("criado_por", "criado_em")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(CondicaoFormulario)
class CondicaoFormularioAdmin(admin.ModelAdmin):
    list_display = ["formulario", "campo_origem", "operador", "valor_comparacao", "acao", "campo_destino", "ativo"]
    list_filter = ["operador", "acao", "ativo"]
    search_fields = ["formulario__titulo", "campo_origem__label", "campo_destino__label"]

    fieldsets = (
        ("Formulário", {"fields": ("formulario",)}),
        ("Condição", {"fields": ("campo_origem", "operador", "valor_comparacao")}),
        ("Ação", {"fields": ("acao", "campo_destino")}),
        ("Status", {"fields": ("ativo",)}),
    )

"""
Admin interface para o módulo de cotações.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Cotacao, CotacaoItem, PropostaFornecedor, PropostaFornecedorItem


class CotacaoItemInline(admin.TabularInline):
    model = CotacaoItem
    extra = 1
    fields = ["ordem", "descricao", "especificacao", "quantidade", "unidade", "produto"]
    ordering = ["ordem"]


@admin.register(Cotacao)
class CotacaoAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "titulo",
        "tenant",
        "status",
        "total_propostas_display",
        "data_abertura",
        "prazo_proposta",
        "criado_por",
    ]
    list_filter = ["status", "tenant", "data_abertura", "criado_por"]
    search_fields = ["codigo", "titulo", "descricao"]
    readonly_fields = ["created_at", "updated_at", "total_propostas_display"]
    inlines = [CotacaoItemInline]

    fieldsets = (
        ("Informações Básicas", {"fields": ("tenant", "codigo", "titulo", "descricao", "status")}),
        ("Prazos e Valores", {"fields": ("data_abertura", "prazo_proposta", "data_encerramento", "valor_estimado")}),
        ("Controle", {"fields": ("criado_por", "observacoes_internas")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("tenant", "criado_por")

    def total_propostas_display(self, obj):
        total = obj.total_propostas
        if total > 0:
            url = reverse("admin:cotacoes_propostafornecedor_changelist") + f"?cotacao__id__exact={obj.id}"
            return format_html('<a href="{}">{} propostas</a>', url, total)
        return "0 propostas"

    total_propostas_display.short_description = "Propostas"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


class PropostaFornecedorItemInline(admin.TabularInline):
    model = PropostaFornecedorItem
    extra = 0
    readonly_fields = ["total_item_display"]
    fields = ["item_cotacao", "preco_unitario", "prazo_entrega_dias", "total_item_display", "observacao_item"]

    def total_item_display(self, obj):
        if obj.pk:
            return f"R$ {obj.total_item:,.2f}"
        return "-"

    total_item_display.short_description = "Total Item"


@admin.register(PropostaFornecedor)
class PropostaFornecedorAdmin(admin.ModelAdmin):
    list_display = [
        "cotacao",
        "fornecedor",
        "status",
        "total_estimado_display",
        "enviado_em",
        "validade_proposta",
        "usuario",
    ]
    list_filter = ["status", "enviado_em", "validade_proposta", "cotacao__tenant"]
    search_fields = ["cotacao__codigo", "cotacao__titulo", "fornecedor__nome_fantasia"]
    readonly_fields = ["created_at", "updated_at", "total_estimado_display"]
    inlines = [PropostaFornecedorItemInline]

    fieldsets = (
        ("Proposta", {"fields": ("cotacao", "fornecedor", "usuario", "status")}),
        ("Valores e Prazos", {"fields": ("total_estimado_display", "validade_proposta", "prazo_entrega_geral")}),
        ("Condições", {"fields": ("condicoes_pagamento", "observacao")}),
        ("Controle", {"fields": ("enviado_em", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cotacao", "fornecedor", "usuario", "cotacao__tenant")

    def total_estimado_display(self, obj):
        return f"R$ {obj.total_estimado:,.2f}"

    total_estimado_display.short_description = "Total Estimado"

    actions = ["enviar_propostas", "selecionar_propostas"]

    def enviar_propostas(self, request, queryset):
        enviadas = 0
        erros = []

        for proposta in queryset.filter(status="rascunho"):
            try:
                proposta.enviar()
                enviadas += 1
            except ValueError as e:
                erros.append(f"{proposta}: {e}")

        if enviadas:
            self.message_user(request, f"{enviadas} propostas enviadas com sucesso.")
        if erros:
            self.message_user(request, f"Erros: {'; '.join(erros)}", level="error")

    enviar_propostas.short_description = "Enviar propostas selecionadas"

    def selecionar_propostas(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Selecione apenas uma proposta.", level="error")
            return

        proposta = queryset.first()
        try:
            proposta.selecionar(request.user)
            self.message_user(request, f"Proposta {proposta} selecionada com sucesso.")
        except ValueError as e:
            self.message_user(request, f"Erro: {e}", level="error")

    selecionar_propostas.short_description = "Selecionar proposta como vencedora"


@admin.register(CotacaoItem)
class CotacaoItemAdmin(admin.ModelAdmin):
    list_display = ["cotacao", "descricao", "quantidade", "unidade", "produto", "ordem"]
    list_filter = ["cotacao__status", "cotacao__tenant", "unidade"]
    search_fields = ["descricao", "especificacao", "cotacao__codigo"]
    ordering = ["cotacao", "ordem"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cotacao", "produto")


@admin.register(PropostaFornecedorItem)
class PropostaFornecedorItemAdmin(admin.ModelAdmin):
    list_display = ["proposta", "item_cotacao_display", "preco_unitario", "total_item_display", "prazo_entrega_dias"]
    list_filter = ["proposta__status", "proposta__cotacao__tenant"]
    search_fields = ["proposta__cotacao__codigo", "item_cotacao__descricao", "proposta__fornecedor__nome_fantasia"]
    readonly_fields = ["total_item_display"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("proposta", "item_cotacao", "proposta__fornecedor", "proposta__cotacao")
        )

    def item_cotacao_display(self, obj):
        return obj.item_cotacao.descricao[:50]

    item_cotacao_display.short_description = "Item"

    def total_item_display(self, obj):
        return f"R$ {obj.total_item:,.2f}"

    total_item_display.short_description = "Total"

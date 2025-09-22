from django.contrib import admin

from .models import AnexoQuantificacao, ItemQuantificacao, ProjetoQuantificacao


class ItemQuantificacaoInline(admin.TabularInline):
    model = ItemQuantificacao
    extra = 0
    fields = ["nome", "unidade_medida", "quantidade", "custo_unitario", "custo_total", "tipo_item"]
    readonly_fields = ["custo_total"]


class AnexoQuantificacaoInline(admin.TabularInline):
    model = AnexoQuantificacao
    extra = 0
    fields = ["nome_arquivo", "arquivo", "tipo_arquivo", "tamanho_arquivo", "upload_por"]
    readonly_fields = ["tamanho_arquivo", "upload_por"]


@admin.register(ProjetoQuantificacao)
class ProjetoQuantificacaoAdmin(admin.ModelAdmin):
    list_display = ["nome", "tenant", "status", "responsavel", "data_inicio", "data_previsao_conclusao"]
    list_filter = ["status", "tenant", "data_inicio"]
    search_fields = ["nome", "descricao"]
    inlines = [ItemQuantificacaoInline, AnexoQuantificacaoInline]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("tenant", "nome", "descricao", "status", "responsavel")}),
        ("Datas", {"fields": ("data_inicio", "data_previsao_conclusao", "created_at", "updated_at")}),
    )


@admin.register(ItemQuantificacao)
class ItemQuantificacaoAdmin(admin.ModelAdmin):
    list_display = ["nome", "projeto", "quantidade", "unidade_medida", "custo_unitario", "custo_total", "tipo_item"]
    list_filter = ["tipo_item", "projeto__tenant"]
    search_fields = ["nome", "observacoes"]
    readonly_fields = ["custo_total", "created_at", "updated_at"]


@admin.register(AnexoQuantificacao)
class AnexoQuantificacaoAdmin(admin.ModelAdmin):
    list_display = ["nome_arquivo", "projeto", "tipo_arquivo", "tamanho_arquivo", "upload_por", "created_at"]
    list_filter = ["tipo_arquivo", "projeto__tenant"]
    search_fields = ["nome_arquivo", "observacoes"]
    readonly_fields = ["tamanho_arquivo", "upload_por", "created_at", "updated_at"]

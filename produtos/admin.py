from django.contrib import admin

from .models import Produto


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "unidade", "preco_unitario", "estoque_atual", "ativo")
    list_filter = ("categoria", "ativo")
    search_fields = ("nome", "descricao")

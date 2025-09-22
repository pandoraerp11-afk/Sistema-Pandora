from django.contrib import admin

from .models import Orcamento


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "obra",
        "cliente",
        "valor_total",
        "data_emissao",
        "status",
    )  # 'descricao' -> 'numero'; 'data_criacao' -> 'data_emissao'
    list_filter = ("status", "data_emissao", "data_validade")  # 'data_criacao' -> 'data_emissao'
    search_fields = (
        "numero",
        "observacoes",
        "obra__nome",
        "cliente__nome_completo",
    )  # 'descricao' -> 'numero' e 'observacoes'
    date_hierarchy = "data_emissao"  # 'data_criacao' -> 'data_emissao'

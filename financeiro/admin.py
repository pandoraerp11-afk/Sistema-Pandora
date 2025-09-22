from django.contrib import admin

from .models import ContaPagar, ContaReceber, Financeiro


@admin.register(Financeiro)
class FinanceiroAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "tipo", "data", "categoria", "status", "obra")
    list_filter = ("tipo", "categoria", "status", "data", "obra")
    search_fields = ("descricao", "obra__nome")
    date_hierarchy = "data"


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = ("descricao", "fornecedor", "valor", "data_vencimento", "data_pagamento", "status")
    list_filter = ("status", "data_vencimento", "fornecedor")
    search_fields = ("descricao", "fornecedor__nome")
    date_hierarchy = "data_vencimento"


@admin.register(ContaReceber)
class ContaReceberAdmin(admin.ModelAdmin):
    list_display = ("descricao", "cliente", "valor", "data_vencimento", "data_recebimento", "status")
    list_filter = ("status", "data_vencimento", "cliente")
    search_fields = ("descricao", "cliente__nome")
    date_hierarchy = "data_vencimento"

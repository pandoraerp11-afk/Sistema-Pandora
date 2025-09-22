# compras/admin.py
from django.contrib import admin

from .models import Compra  # CORRETO


@admin.register(Compra)  # CORRETO
class CompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "fornecedor", "obra", "data_pedido", "valor_total", "status")
    list_filter = ("status", "data_pedido", "forma_pagamento")
    search_fields = ("numero", "observacoes", "fornecedor__nome_empresa", "obra__nome")
    date_hierarchy = "data_pedido"

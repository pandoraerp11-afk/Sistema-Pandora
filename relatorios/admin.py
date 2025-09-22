# relatorios/admin.py
from django.contrib import admin

from .models import Relatorio  # CORRETO


@admin.register(Relatorio)  # CORRETO
class RelatoriosAdmin(admin.ModelAdmin):  # O nome da classe Admin pode ser plural
    list_display = ("titulo", "data_criacao", "tipo")
    list_filter = ("tipo", "data_criacao")
    search_fields = ("titulo", "descricao")
    date_hierarchy = "data_criacao"

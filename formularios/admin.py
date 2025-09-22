# formularios/admin.py
from django.contrib import admin

from .models import Formulario  # CORRETO


@admin.register(Formulario)  # CORRETO
class FormulariosAdmin(admin.ModelAdmin):  # O nome da classe Admin pode ser plural
    list_display = ("titulo", "tipo", "data_criacao", "ativo")
    list_filter = ("tipo", "ativo", "data_criacao")
    search_fields = ("titulo", "descricao")
    date_hierarchy = "data_criacao"

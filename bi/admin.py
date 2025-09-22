# bi/admin.py
from django.contrib import admin

from .models import Indicador  # CORRETO


@admin.register(Indicador)  # CORRETO
class BiAdmin(admin.ModelAdmin):  # O nome da classe Admin pode ser BiAdmin
    list_display = ("nome", "valor", "data", "tipo")
    list_filter = ("tipo", "data")
    search_fields = ("nome", "descricao")
    date_hierarchy = "data"

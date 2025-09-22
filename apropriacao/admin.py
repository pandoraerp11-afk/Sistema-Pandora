# apropriacao/admin.py
from django.contrib import admin

from .models import Apropriacao  # CORRETO


@admin.register(Apropriacao)  # CORRETO
class ApropriacaoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "obra", "data", "responsavel")
    list_filter = ("data", "obra")
    search_fields = ("descricao", "obra__nome", "responsavel__nome")  # Assumindo que Obra e Funcionario têm 'nome'
    date_hierarchy = "data"

# treinamento/admin.py
from django.contrib import admin

from .models import Treinamento  # CORRETO


@admin.register(Treinamento)  # CORRETO
class TreinamentoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "instrutor", "data_inicio", "data_fim", "carga_horaria", "local")
    list_filter = ("data_inicio", "data_fim", "instrutor")  # Adicionei instrutor ao filtro
    search_fields = (
        "titulo",
        "descricao",
        "instrutor__nome_completo",
        "local",
    )  # Assumindo que Funcionario tem nome_completo
    date_hierarchy = "data_inicio"

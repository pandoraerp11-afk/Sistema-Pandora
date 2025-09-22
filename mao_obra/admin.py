# mao_obra/admin.py
from django.contrib import admin

from .models import MaoObra  # CORRETO


@admin.register(MaoObra)  # CORRETO
class MaoObraAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "atividade", "obra", "data", "horas_trabalhadas", "valor_hora")
    list_filter = ("data", "obra", "funcionario")
    search_fields = ("atividade", "funcionario__nome", "obra__nome")  # Assumindo que Funcionario e Obra têm 'nome'
    date_hierarchy = "data"

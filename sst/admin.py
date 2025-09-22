# sst/admin.py
from django.contrib import admin

from .models import DocumentoSST  # CORRETO


@admin.register(DocumentoSST)  # CORRETO
class SSTAdmin(admin.ModelAdmin):  # O nome da classe Admin pode ser SSTAdmin
    list_display = ("titulo", "tipo", "data_criacao", "data_atualizacao", "responsavel")  # Adicionei data_atualizacao
    list_filter = ("tipo", "data_criacao", "data_atualizacao", "responsavel")  # Adicionei responsavel
    search_fields = ("titulo", "descricao", "responsavel__nome_completo")  # Assumindo que Funcionario tem nome_completo
    date_hierarchy = "data_criacao"

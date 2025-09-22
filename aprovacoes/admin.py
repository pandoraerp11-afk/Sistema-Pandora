# aprovacoes/admin.py
from django.contrib import admin

from .models import Aprovacao


@admin.register(Aprovacao)
class AprovacoesAdmin(admin.ModelAdmin):
    list_display = ("titulo", "descricao", "status", "solicitante", "aprovador", "data_solicitacao", "data_aprovacao")
    list_filter = ("status", "tipo_aprovacao", "prioridade", "data_solicitacao", "data_aprovacao")
    search_fields = ("titulo", "descricao", "solicitante__username", "aprovador__username")
    date_hierarchy = "data_solicitacao"
    readonly_fields = ("data_solicitacao",)

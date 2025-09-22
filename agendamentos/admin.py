from django.contrib import admin

from .models import ProfissionalProcedimento


@admin.register(ProfissionalProcedimento)
class ProfissionalProcedimentoAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "profissional", "servico", "ativo", "created_at")
    list_filter = ("ativo", "tenant")
    search_fields = (
        "profissional__first_name",
        "profissional__last_name",
        "profissional__email",
        "servico__nome_servico",
    )
    autocomplete_fields = ("tenant", "profissional", "servico")

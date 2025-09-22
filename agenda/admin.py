from django.contrib import admin

from .models import AgendaConfiguracao, Evento, EventoLembrete


class EventoLembreteInline(admin.TabularInline):
    model = EventoLembrete
    extra = 0
    fields = ("usuario", "minutos_antes", "ativo")
    autocomplete_fields = ("usuario",)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "data_inicio", "data_fim", "dia_inteiro", "status", "prioridade")
    list_filter = ("data_inicio", "dia_inteiro", "status", "prioridade")
    search_fields = ("titulo", "descricao", "local")
    date_hierarchy = "data_inicio"
    inlines = [EventoLembreteInline]


@admin.register(AgendaConfiguracao)
class AgendaConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ("tenant", "digest_email_habilitado", "digest_email_hora")
    search_fields = ("tenant__name",)

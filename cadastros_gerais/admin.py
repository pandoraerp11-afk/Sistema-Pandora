# cadastros_gerais/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AlvoAplicacao, CategoriaAuxiliar, ItemAuxiliar, UnidadeMedida


@admin.register(UnidadeMedida)
class UnidadeMedidaAdmin(admin.ModelAdmin):
    """
    Configuração da interface de administração para Unidades de Medida.
    """

    list_display = ("nome", "simbolo", "descricao_resumida")
    search_fields = ("nome", "simbolo", "descricao")

    def descricao_resumida(self, obj):
        """Retorna uma versão curta da descrição para a lista."""
        if obj.descricao and len(obj.descricao) > 75:
            return obj.descricao[:75] + "..."
        return obj.descricao or "-"

    descricao_resumida.short_description = _("Descrição")


@admin.register(CategoriaAuxiliar)
class CategoriaAuxiliarAdmin(admin.ModelAdmin):
    """
    Configuração da interface de administração para Categorias Auxiliares.
    """

    list_display = ("nome", "slug", "ativo", "ordem")
    search_fields = ("nome", "slug", "descricao")
    list_filter = ("ativo",)
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("ordem", "nome")


@admin.register(ItemAuxiliar)
class ItemAuxiliarAdmin(admin.ModelAdmin):
    """
    Configuração da interface de administração para Itens Auxiliares.
    """

    list_display = ("nome", "categoria", "alvos_admin", "versionavel", "periodicidade", "ativo", "ordem")
    list_filter = ("categoria", "ativo", "targets", "versionavel", "periodicidade")
    search_fields = ("nome", "slug", "descricao", "categoria__nome")
    autocomplete_fields = ("categoria", "targets")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "categoria",
                    "nome",
                    "slug",
                    "descricao",
                    "targets",
                    "versionavel",
                    "periodicidade",
                    "ativo",
                    "ordem",
                )
            },
        ),
        (
            _("Configuração (JSON)"),
            {
                "fields": ("config",),
                "description": _(
                    "Armazene metadados como obrigatório, validade_dias, tipos_arquivo, icon_class, url_pattern, etc."
                ),
            },
        ),
    )

    def alvos_admin(self, obj):
        return obj.alvos_display

    alvos_admin.short_description = _("Aplicado em")


@admin.register(AlvoAplicacao)
class AlvoAplicacaoAdmin(admin.ModelAdmin):
    list_display = ("code", "nome")
    search_fields = ("code", "nome")

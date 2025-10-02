"""Admin registrations para Portal Cliente (multi-tenant config & contas)."""

from __future__ import annotations

from django.contrib import admin

from .models import ContaCliente, DocumentoPortalCliente, PortalClienteConfiguracao


@admin.register(PortalClienteConfiguracao)
class PortalClienteConfiguracaoAdmin(admin.ModelAdmin):
    """Admin para configuração multi-tenant do Portal Cliente.

    Permite ajustar janelas temporais e limites de throttling específicos
    por tenant sem necessidade de novo deploy.
    """

    list_display = (
        "tenant",
        "checkin_antecedencia_min",
        "checkin_tolerancia_pos_min",
        "finalizacao_tolerancia_horas",
        "cancelamento_limite_horas",
        "throttle_checkin",
        "throttle_finalizar",
        "throttle_avaliar",
        "updated_at",
    )
    search_fields = ("tenant__nome", "tenant__subdominio")
    # list_filter não aceita lookups com dupla underscore para campos relacionados.
    # O uso anterior ("tenant__subdominio",) gerou admin.E116. Para permitir filtro por tenant
    # basta usar o próprio FK. A busca por subdomínio permanece via search_fields.
    list_filter = ("tenant",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("tenant",)}),
        (
            "Janelas Temporais",
            {
                "fields": (
                    "checkin_antecedencia_min",
                    "checkin_tolerancia_pos_min",
                    "finalizacao_tolerancia_horas",
                    "cancelamento_limite_horas",
                ),
            },
        ),
        ("Throttling", {"fields": ("throttle_checkin", "throttle_finalizar", "throttle_avaliar")}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ContaCliente)
class ContaClienteAdmin(admin.ModelAdmin):
    """Admin básico para contas de clientes do portal."""

    list_display = ("id", "cliente", "usuario", "ativo", "is_admin_portal", "data_ultimo_acesso")
    list_filter = ("ativo", "is_admin_portal")
    search_fields = ("cliente__nome", "usuario__username")
    autocomplete_fields = ("cliente", "usuario", "concedido_por")
    readonly_fields = ("created_at", "updated_at", "data_ultimo_acesso")


@admin.register(DocumentoPortalCliente)
class DocumentoPortalClienteAdmin(admin.ModelAdmin):
    """Admin para documentos expostos ao cliente no portal."""

    list_display = ("id", "conta", "documento_versao", "ativo", "expiracao_visualizacao", "updated_at")
    list_filter = ("ativo",)
    search_fields = ("conta__cliente__nome", "documento_versao__documento__titulo")
    readonly_fields = ("created_at", "updated_at")

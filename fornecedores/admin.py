# fornecedores/admin.py (VERSÃO FINAL, FIEL AO SEU MODELO "DE PONTA")

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    CategoriaFornecedor,
    ContatoFornecedor,
    DadosBancariosFornecedor,
    EnderecoFornecedor,
    Fornecedor,
    FornecedorPF,
    FornecedorPJ,
)


class FornecedorPJInline(admin.StackedInline):
    model = FornecedorPJ
    can_delete = False
    verbose_name_plural = "Dados de Pessoa Jurídica"


class FornecedorPFInline(admin.StackedInline):
    model = FornecedorPF
    can_delete = False
    verbose_name_plural = "Dados de Pessoa Física"


class ContatoFornecedorInline(admin.TabularInline):
    model = ContatoFornecedor
    extra = 1
    classes = ("collapse",)


class EnderecoFornecedorInline(admin.TabularInline):
    model = EnderecoFornecedor
    extra = 1
    classes = ("collapse",)


class DadosBancariosFornecedorInline(admin.TabularInline):
    model = DadosBancariosFornecedor
    extra = 1
    classes = ("collapse",)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("get_nome_display", "get_documento_principal", "tipo_pessoa", "status", "categoria", "tenant_link")
    list_filter = ("status", "tipo_pessoa", "categoria", "tenant")
    search_fields = (
        "pessoajuridica__nome_fantasia",
        "pessoajuridica__razao_social",
        "pessoajuridica__cnpj",
        "pessoafisica__nome_completo",
        "pessoafisica__cpf",
    )
    inlines = [
        FornecedorPJInline,
        FornecedorPFInline,
        ContatoFornecedorInline,
        EnderecoFornecedorInline,
        DadosBancariosFornecedorInline,
    ]

    fieldsets = (
        (
            _("Identificação Principal"),
            {"fields": ("tenant", ("tipo_pessoa", "tipo_fornecimento"), "categoria", "logo")},
        ),
        (_("Status e Controle"), {"fields": ("status", "status_homologacao", "avaliacao")}),
        (_("Termos e Observações"), {"classes": ("collapse",), "fields": ("condicoes_pagamento", "observacoes")}),
    )

    @admin.display(description="Nome / Fantasia", ordering="pessoajuridica__nome_fantasia")
    def get_nome_display(self, obj):
        return obj.__str__()

    @admin.display(description="CNPJ / CPF")
    def get_documento_principal(self, obj):
        if hasattr(obj, "pessoajuridica"):
            return obj.pessoajuridica.cnpj
        if hasattr(obj, "pessoafisica"):
            return obj.pessoafisica.cpf
        return "N/A"

    @admin.display(description="Empresa (Tenant)", ordering="tenant__name")
    def tenant_link(self, obj):
        if obj.tenant:
            link = reverse("admin:core_tenant_change", args=[obj.tenant.id])
            return format_html('<a href="{}">{}</a>', link, obj.tenant.name)
        return "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("pessoafisica", "pessoajuridica", "tenant", "categoria")
        if request.user.is_superuser:
            return qs
        tenant_user = request.user.tenant_memberships.first()
        if tenant_user:
            return qs.filter(tenant=tenant_user.tenant)
        return qs.none()


@admin.register(CategoriaFornecedor)
class CategoriaFornecedorAdmin(admin.ModelAdmin):
    list_display = ("nome", "tenant")
    list_filter = ("tenant",)
    search_fields = ("nome",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant_user = request.user.tenant_memberships.first()
        if tenant_user:
            return qs.filter(tenant=tenant_user.tenant)
        return qs.none()

"""Admin do app clientes.

Responsável por cadastro e visualização de Clientes e entidades relacionadas.
Documentos específicos do cliente foram migrados para o app 'documentos';
este módulo removeu inlines/admins de modelos legados (DocumentoCliente) e
otimiza queries com select_related.
"""

from typing import ClassVar

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Cliente, Contato, EnderecoAdicional, PessoaFisica, PessoaJuridica

CPF_LENGTH = 11
CNPJ_LENGTH = 14


class ContatoInline(admin.TabularInline):
    """Inline para contatos adicionais do cliente."""

    model = Contato
    extra = 1  # Quantos formulários em branco mostrar
    fields = ("tipo", "valor", "nome_contato_responsavel", "cargo", "principal", "observacao")
    verbose_name = _("Contato Adicional")
    verbose_name_plural = _("Contatos Adicionais")
    # Adicionar classes para melhor renderização se usar django-jazzmin ou similar


class EnderecoAdicionalInline(admin.TabularInline):
    """Inline para endereços adicionais associados ao cliente."""

    model = EnderecoAdicional
    extra = 1
    fields = (
        "tipo",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cidade",
        "estado",
        "cep",
        "ponto_referencia",
        "principal",
    )
    verbose_name = _("Endereço Adicional")
    verbose_name_plural = _("Endereços Adicionais")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """Admin principal de Cliente (documentos migrados para app 'documentos')."""

    list_display = (
        "id",
        "nome_display_link",
        "tipo",
        "documento_principal_formatado",
        "email",
        "telefone",
        "cidade",
        "estado",
        "ativo",
        "data_cadastro",
    )
    list_filter = ("tipo", "ativo", "data_cadastro", "estado", "cidade")
    search_fields = (
        "id",
        "email",
        "telefone",
        "pessoafisica__nome_completo",
        "pessoafisica__cpf",
        "pessoajuridica__razao_social",
        "pessoajuridica__nome_fantasia",
        "pessoajuridica__cnpj",
        "endereco",  # Campo de endereço principal do Cliente
        "bairro",
        "cidade",
        "cep",
    )
    date_hierarchy = "data_cadastro"
    ordering = ("-id",)
    list_per_page = 20
    # Removido DocumentoClienteInline: documentos agora são geridos pelo app 'documentos'.
    inlines: ClassVar[list[type[admin.TabularInline]]] = [ContatoInline, EnderecoAdicionalInline]

    fieldsets = (
        (
            None,
            {
                # Campo tipo deve vir primeiro para a lógica condicional de PF/PJ
                "fields": ("tipo",),
            },
        ),
        (_("Informações de Contato Principal"), {"fields": ("email", "telefone")}),
        (
            _("Endereço Principal"),
            {
                "classes": ("collapse",),  # Para colapsar a secção por defeito
                "fields": ("endereco", "complemento", "bairro", "cidade", "estado", "cep"),
            },
        ),
        (_("Outras Informações"), {"classes": ("collapse",), "fields": ("observacoes", "ativo")}),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Cliente]:
        """Otimiza seleção de dados relacionados para reduzir queries N+1."""
        qs = super().get_queryset(request)
        return qs.select_related("pessoafisica", "pessoajuridica")

    @admin.display(description=_("Nome/Razão Social"), ordering="pessoafisica__nome_completo")
    def nome_display_link(self, obj: Cliente) -> str:
        """Retorna link HTML para a edição do cliente no admin."""
        link = reverse("admin:clientes_cliente_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.nome_display)

    @admin.display(description=_("CPF/CNPJ"), ordering="pessoafisica__cpf")
    def documento_principal_formatado(self, obj: Cliente) -> str | None:
        """Formata CPF ou CNPJ conforme tipo de cliente."""
        doc = obj.documento_principal
        if obj.tipo == "PF" and doc and len(doc) == CPF_LENGTH:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        if obj.tipo == "PJ" and doc and len(doc) == CNPJ_LENGTH:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc


@admin.register(PessoaFisica)
class PessoaFisicaAdmin(admin.ModelAdmin):
    """Admin para dados de pessoa física vinculados a Cliente."""

    list_display = ("nome_completo", "cpf_formatado", "rg", "data_nascimento", "cliente_link_display")
    search_fields = ("nome_completo", "cpf", "rg", "cliente__email", "cliente__id")
    list_filter = ("estado_civil", "nacionalidade", "cliente__ativo")
    raw_id_fields = ("cliente",)  # Melhora performance para ForeignKey com muitos objetos
    readonly_fields = ("cliente_link_display",)  # Para exibir o link sem permitir edição direta do ID

    @admin.display(description=_("CPF"), ordering="cpf")
    def cpf_formatado(self, obj: PessoaFisica) -> str | None:
        """Formata CPF em padrão 000.000.000-00 se comprimento esperado."""
        if obj.cpf and len(obj.cpf) == CPF_LENGTH:
            return f"{obj.cpf[:3]}.{obj.cpf[3:6]}.{obj.cpf[6:9]}-{obj.cpf[9:]}"
        return obj.cpf

    @admin.display(description=_("Cliente Associado"))
    def cliente_link_display(self, obj: PessoaFisica) -> str:
        """Link para o cliente relacionado."""
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{} (ID: {})</a>', link, obj.cliente.nome_display, obj.cliente.id)
        return "-"


@admin.register(PessoaJuridica)
class PessoaJuridicaAdmin(admin.ModelAdmin):
    """Admin para dados de pessoa jurídica vinculados a Cliente."""

    list_display = ("razao_social", "nome_fantasia", "cnpj_formatado", "inscricao_estadual", "cliente_link_display")
    search_fields = ("razao_social", "nome_fantasia", "cnpj", "cliente__email", "cliente__id")
    list_filter = ("porte_empresa", "ramo_atividade", "cliente__ativo")
    raw_id_fields = ("cliente",)
    readonly_fields = ("cliente_link_display",)

    @admin.display(description=_("CNPJ"), ordering="cnpj")
    def cnpj_formatado(self, obj: PessoaJuridica) -> str | None:
        """Formata CNPJ em padrão 00.000.000/0000-00 se comprimento esperado."""
        if obj.cnpj and len(obj.cnpj) == CNPJ_LENGTH:
            return f"{obj.cnpj[:2]}.{obj.cnpj[2:5]}.{obj.cnpj[5:8]}/{obj.cnpj[8:12]}-{obj.cnpj[12:]}"
        return obj.cnpj

    @admin.display(description=_("Cliente Associado"))
    def cliente_link_display(self, obj: PessoaJuridica) -> str:
        """Link para o cliente relacionado."""
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{} (ID: {})</a>', link, obj.cliente.nome_display, obj.cliente.id)
        return "-"


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    """Admin para contatos adicionais relacionados a clientes."""

    list_display = ("cliente_nome_link", "tipo", "valor", "nome_contato_responsavel", "principal")
    list_filter = ("tipo", "principal", "cliente__tipo")
    search_fields = (
        "valor",
        "nome_contato_responsavel",
        "cliente__pessoafisica__nome_completo",
        "cliente__pessoajuridica__razao_social",
        "cliente__email",
    )
    autocomplete_fields: ClassVar[list[str]] = ["cliente"]
    list_select_related: ClassVar[list[str]] = ["cliente__pessoafisica", "cliente__pessoajuridica"]

    @admin.display(description=_("Cliente"), ordering="cliente__pessoafisica__nome_completo")
    def cliente_nome_link(self, obj: Contato) -> str:
        """Link para o cliente do contato."""
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.cliente.nome_display)
        return "-"


@admin.register(EnderecoAdicional)
class EnderecoAdicionalAdmin(admin.ModelAdmin):
    """Admin para endereços adicionais de clientes."""

    list_display = ("cliente_nome_link", "tipo", "logradouro_completo", "cidade", "estado", "principal")
    list_filter = ("tipo", "estado", "principal", "cidade", "cliente__tipo")
    search_fields = (
        "logradouro",
        "bairro",
        "cidade",
        "cep",
        "cliente__pessoafisica__nome_completo",
        "cliente__pessoajuridica__razao_social",
        "cliente__email",
    )
    autocomplete_fields: ClassVar[list[str]] = ["cliente"]
    list_select_related: ClassVar[list[str]] = ["cliente__pessoafisica", "cliente__pessoajuridica"]

    @admin.display(description=_("Cliente"), ordering="cliente__pessoafisica__nome_completo")
    def cliente_nome_link(self, obj: EnderecoAdicional) -> str:
        """Link para o cliente relacionado ao endereço."""
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.cliente.nome_display)
        return "-"

    @admin.display(description=_("Endereço"))
    def logradouro_completo(self, obj: EnderecoAdicional) -> str:
        """Concatena logradouro e número para exibição."""
        return f"{obj.logradouro}, {obj.numero}"

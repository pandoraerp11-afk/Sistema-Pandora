from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Cliente, Contato, DocumentoCliente, EnderecoAdicional, PessoaFisica, PessoaJuridica


# Inlines para adicionar diretamente na página do Cliente
class ContatoInline(admin.TabularInline):
    model = Contato
    extra = 1  # Quantos formulários em branco mostrar
    fields = ("tipo", "valor", "nome_contato_responsavel", "cargo", "principal", "observacao")
    verbose_name = _("Contato Adicional")
    verbose_name_plural = _("Contatos Adicionais")
    # Adicionar classes para melhor renderização se usar django-jazzmin ou similar
    # classes = ['collapse']


class EnderecoAdicionalInline(admin.TabularInline):
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
    # classes = ['collapse']


class DocumentoClienteInline(admin.TabularInline):
    model = DocumentoCliente
    extra = 1
    fields = ("tipo", "nome_documento", "arquivo", "descricao", "data_validade")
    readonly_fields = ("data_upload", "filename")  # data_upload é auto_now_add, filename é uma property
    verbose_name = _("Documento do Cliente")
    verbose_name_plural = _("Documentos do Cliente")
    # classes = ['collapse']


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
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
    inlines = [ContatoInline, EnderecoAdicionalInline, DocumentoClienteInline]

    fieldsets = (
        (
            None,
            {  # Campo tipo deve vir primeiro para a lógica condicional de PF/PJ (se implementada via JS no admin)
                "fields": ("tipo",)
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

    def get_queryset(self, request):
        # Otimizar consulta para nome_display e documento_principal
        qs = super().get_queryset(request)
        return qs.select_related("pessoafisica", "pessoajuridica")

    def nome_display_link(self, obj):
        # Cria um link para a página de edição do cliente
        link = reverse("admin:clientes_cliente_change", args=[obj.id])
        return format_html('<a href="{}">{}</a>', link, obj.nome_display)

    nome_display_link.short_description = _("Nome/Razão Social")
    nome_display_link.admin_order_field = "pessoafisica__nome_completo"  # Ou 'pessoajuridica__razao_social' - pode precisar de lógica mais complexa se quiser ordenar por ambos

    def documento_principal_formatado(self, obj):
        doc = obj.documento_principal
        if obj.tipo == "PF" and doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # Formata CPF
        elif obj.tipo == "PJ" and doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # Formata CNPJ
        return doc

    documento_principal_formatado.short_description = _("CPF/CNPJ")
    documento_principal_formatado.admin_order_field = "pessoafisica__cpf"  # Ou 'pessoajuridica__cnpj'


@admin.register(PessoaFisica)
class PessoaFisicaAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "cpf_formatado", "rg", "data_nascimento", "cliente_link_display")
    search_fields = ("nome_completo", "cpf", "rg", "cliente__email", "cliente__id")
    list_filter = ("estado_civil", "nacionalidade", "cliente__ativo")
    raw_id_fields = ("cliente",)  # Melhora performance para ForeignKey com muitos objetos
    readonly_fields = ("cliente_link_display",)  # Para exibir o link sem permitir edição direta do ID

    def cpf_formatado(self, obj):
        if obj.cpf and len(obj.cpf) == 11:
            return f"{obj.cpf[:3]}.{obj.cpf[3:6]}.{obj.cpf[6:9]}-{obj.cpf[9:]}"
        return obj.cpf

    cpf_formatado.short_description = _("CPF")
    cpf_formatado.admin_order_field = "cpf"

    def cliente_link_display(self, obj):
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{} (ID: {})</a>', link, obj.cliente.nome_display, obj.cliente.id)
        return "-"

    cliente_link_display.short_description = _("Cliente Associado")


@admin.register(PessoaJuridica)
class PessoaJuridicaAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "nome_fantasia", "cnpj_formatado", "inscricao_estadual", "cliente_link_display")
    search_fields = ("razao_social", "nome_fantasia", "cnpj", "cliente__email", "cliente__id")
    list_filter = ("porte_empresa", "ramo_atividade", "cliente__ativo")
    raw_id_fields = ("cliente",)
    readonly_fields = ("cliente_link_display",)

    def cnpj_formatado(self, obj):
        if obj.cnpj and len(obj.cnpj) == 14:
            return f"{obj.cnpj[:2]}.{obj.cnpj[2:5]}.{obj.cnpj[5:8]}/{obj.cnpj[8:12]}-{obj.cnpj[12:]}"
        return obj.cnpj

    cnpj_formatado.short_description = _("CNPJ")
    cnpj_formatado.admin_order_field = "cnpj"

    def cliente_link_display(self, obj):
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{} (ID: {})</a>', link, obj.cliente.nome_display, obj.cliente.id)
        return "-"

    cliente_link_display.short_description = _("Cliente Associado")


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    list_display = ("cliente_nome_link", "tipo", "valor", "nome_contato_responsavel", "principal")
    list_filter = ("tipo", "principal", "cliente__tipo")
    search_fields = (
        "valor",
        "nome_contato_responsavel",
        "cliente__pessoafisica__nome_completo",
        "cliente__pessoajuridica__razao_social",
        "cliente__email",
    )
    autocomplete_fields = ["cliente"]
    list_select_related = ["cliente__pessoafisica", "cliente__pessoajuridica"]  # Otimiza a busca do nome do cliente

    def cliente_nome_link(self, obj):
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.cliente.nome_display)
        return "-"

    cliente_nome_link.short_description = _("Cliente")
    cliente_nome_link.admin_order_field = "cliente__pessoafisica__nome_completo"  # Ajustar se necessário para PJ


@admin.register(EnderecoAdicional)
class EnderecoAdicionalAdmin(admin.ModelAdmin):
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
    autocomplete_fields = ["cliente"]
    list_select_related = ["cliente__pessoafisica", "cliente__pessoajuridica"]

    def cliente_nome_link(self, obj):
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.cliente.nome_display)
        return "-"

    cliente_nome_link.short_description = _("Cliente")
    cliente_nome_link.admin_order_field = "cliente__pessoafisica__nome_completo"

    def logradouro_completo(self, obj):
        return f"{obj.logradouro}, {obj.numero}"

    logradouro_completo.short_description = _("Endereço")


@admin.register(DocumentoCliente)
class DocumentoClienteAdmin(admin.ModelAdmin):
    list_display = ("cliente_nome_link", "tipo", "nome_documento", "data_upload", "data_validade", "ver_arquivo")
    list_filter = ("tipo", "data_upload", "data_validade", "cliente__tipo")
    search_fields = (
        "nome_documento",
        "descricao",
        "cliente__pessoafisica__nome_completo",
        "cliente__pessoajuridica__razao_social",
        "cliente__email",
    )
    date_hierarchy = "data_upload"
    autocomplete_fields = ["cliente"]
    readonly_fields = ("data_upload", "filename_display")
    list_select_related = ["cliente__pessoafisica", "cliente__pessoajuridica"]

    fields = (
        "cliente",
        "tipo",
        "nome_documento",
        "arquivo",
        "filename_display",
        "descricao",
        "data_validade",
        "data_upload",
    )

    def cliente_nome_link(self, obj):
        if obj.cliente:
            link = reverse("admin:clientes_cliente_change", args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.cliente.nome_display)
        return "-"

    cliente_nome_link.short_description = _("Cliente")
    cliente_nome_link.admin_order_field = "cliente__pessoafisica__nome_completo"

    def ver_arquivo(self, obj):
        if obj.arquivo:
            # Idealmente, esta URL deveria apontar para uma view de download segura,
            # mas para o admin, o link direto pode ser suficiente se o MEDIA_URL estiver configurado.
            return format_html('<a href="{}" target="_blank">{}</a>', obj.arquivo.url, obj.filename)
        return _("Nenhum arquivo")

    ver_arquivo.short_description = _("Arquivo")

    def filename_display(self, obj):
        return obj.filename

    filename_display.short_description = _("Nome do Ficheiro Original")

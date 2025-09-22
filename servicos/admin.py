# servicos/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Avaliacao,
    CategoriaServico,
    RegraCobranca,
    Servico,
    ServicoDocumento,
    ServicoFornecedor,
    ServicoImagem,
)


class ServicoImagemInline(admin.TabularInline):
    model = ServicoImagem
    extra = 1
    readonly_fields = ("imagem_preview",)
    fields = ("imagem", "imagem_preview", "titulo", "descricao", "ordem")
    verbose_name = _("Imagem Adicional")
    verbose_name_plural = _("Imagens Adicionais")

    def imagem_preview(self, obj):
        if obj.imagem:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 100px; max-width: 100px;" /></a>',
                obj.imagem.url,
            )
        return _("(Nenhuma imagem)")

    imagem_preview.short_description = _("Preview")


class ServicoDocumentoInline(admin.TabularInline):
    model = ServicoDocumento
    extra = 1
    fields = ("titulo", "arquivo", "tipo", "filename")
    readonly_fields = ("filename",)
    verbose_name = _("Documento Anexo")
    verbose_name_plural = _("Documentos Anexos")


class AvaliacaoInline(admin.StackedInline):
    model = Avaliacao
    extra = 0
    fields = ("nome_cliente_link", "nota", "comentario_resumido", "aprovado", "data_avaliacao")
    readonly_fields = ("nome_cliente_link", "nota", "comentario_resumido", "data_avaliacao")
    can_delete = True
    verbose_name = _("Avaliação Recebida")
    verbose_name_plural = _("Avaliações Recebidas")
    show_change_link = True
    ordering = ("-data_avaliacao",)

    def nome_cliente_link(self, obj):
        if obj.id:
            link = reverse("admin:servicos_avaliacao_change", args=[obj.id])
            return format_html('<a href="{}">{}</a>', link, obj.nome_cliente)
        return obj.nome_cliente

    nome_cliente_link.short_description = _("Cliente")

    def comentario_resumido(self, obj):
        return (obj.comentario[:75] + "...") if obj.comentario and len(obj.comentario) > 75 else obj.comentario

    comentario_resumido.short_description = _("Comentário")


class ServicoFornecedorInline(admin.TabularInline):
    model = ServicoFornecedor
    extra = 1
    autocomplete_fields = ["fornecedor", "regra_cobranca_fornecedor"]
    verbose_name = _("Fornecedor do Serviço")
    verbose_name_plural = _("Fornecedores e Preços")
    fields = ("fornecedor", "preco_base_fornecedor", "regra_cobranca_fornecedor", "codigo_fornecedor")


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = (
        "nome_servico",
        "codigo",
        "tipo_servico",
        "categoria_link",
        "ativo",
        "destaque",
        "data_cadastro_formatada",
    )
    list_filter = ("tipo_servico", "categoria", "ativo", "destaque")
    search_fields = ("nome_servico", "slug", "descricao", "codigo", "categoria__nome")
    readonly_fields = ("data_cadastro", "ultima_atualizacao", "slug", "codigo")
    prepopulated_fields = {"slug": ("nome_servico",)}
    fieldsets = (
        (None, {"fields": ("tipo_servico", "nome_servico", "slug", "codigo", "categoria", "imagem_principal")}),
        (
            _("Descrições e Conteúdo"),
            {
                "classes": ("collapse",),
                "fields": (
                    "descricao_curta",
                    "descricao",
                    "materiais_inclusos",
                    "materiais_nao_inclusos",
                    "requisitos",
                ),
            },
        ),
        (
            _("Precificação Padrão (Venda)"),
            {"fields": ("preco_base", "regra_cobranca", "tempo_estimado", "prazo_entrega")},
        ),
        (
            _("Disponibilidade e Opções"),
            {"classes": ("collapse",), "fields": ("disponivel_online", "requer_visita_tecnica", "requer_aprovacao")},
        ),
        (_("Marketing e SEO"), {"classes": ("collapse",), "fields": ("palavras_chave", "destaque")}),
        (_("Controle"), {"fields": ("ativo", ("data_cadastro", "ultima_atualizacao"))}),
    )
    inlines_ofertado = [ServicoImagemInline, ServicoDocumentoInline, AvaliacaoInline]
    inlines_recebido = [ServicoFornecedorInline, ServicoImagemInline, ServicoDocumentoInline]

    def get_inlines(self, request, obj=None):
        if obj and obj.tipo_servico == "RECEBIDO":
            return self.inlines_recebido
        return self.inlines_ofertado

    def categoria_link(self, obj):
        if obj.categoria:
            link = reverse("admin:servicos_categoriaservico_change", args=[obj.categoria.id])
            return format_html('<a href="{}">{}</a>', link, obj.categoria.nome)
        return "-"

    categoria_link.short_description = _("Categoria")
    categoria_link.admin_order_field = "categoria__nome"

    def data_cadastro_formatada(self, obj):
        return obj.data_cadastro.strftime("%d/%m/%Y %H:%M") if obj.data_cadastro else "-"

    data_cadastro_formatada.short_description = _("Data Cadastro")
    data_cadastro_formatada.admin_order_field = "data_cadastro"


@admin.register(CategoriaServico)
class CategoriaServicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "descricao_resumida", "ativo", "contagem_servicos_link")
    list_filter = ("ativo",)
    search_fields = ("nome", "descricao", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    fields = ("nome", "slug", "descricao", "ativo")

    def descricao_resumida(self, obj):
        return (obj.descricao[:75] + "...") if obj.descricao and len(obj.descricao) > 75 else obj.descricao

    descricao_resumida.short_description = _("Descrição")

    def contagem_servicos_link(self, obj):
        count = obj.servicos.count()
        url = reverse("admin:servicos_servico_changelist") + f"?categoria__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)

    contagem_servicos_link.short_description = _("Nº de Serviços")


@admin.register(RegraCobranca)
class RegraCobrancaAdmin(admin.ModelAdmin):
    list_display = ("nome", "unidade_medida_link", "valor_base_formatado", "tipo_calculo", "ativo")
    list_filter = ("tipo_calculo", "ativo", "unidade_medida")
    search_fields = ("nome", "descricao", "unidade_medida__nome")
    list_select_related = ("unidade_medida",)
    fields = (
        "nome",
        "descricao",
        "unidade_medida",
        "valor_base",
        "valor_minimo",
        "incremento",
        "taxa_adicional",
        "tipo_calculo",
        "formula_personalizada",
        "ativo",
    )

    def unidade_medida_link(self, obj):
        if obj.unidade_medida:
            link = reverse("admin:cadastros_gerais_unidademedida_change", args=[obj.unidade_medida.id])
            return format_html('<a href="{}">{}</a>', link, obj.unidade_medida)
        return "-"

    unidade_medida_link.short_description = _("Unidade de Medida")
    unidade_medida_link.admin_order_field = "unidade_medida__nome"

    def valor_base_formatado(self, obj):
        return f"R$ {obj.valor_base:_.2f}".replace(".", ",").replace("_", ".")

    valor_base_formatado.short_description = _("Valor Base")


# O resto dos seus arquivos de admin (ServicoImagemAdmin, etc.) permanecem iguais
# Por consistência, listo-os aqui.


@admin.register(ServicoImagem)
class ServicoImagemAdmin(admin.ModelAdmin):
    list_display = ("servico_link", "titulo_display", "imagem_preview_list", "ordem", "data_upload_formatada")
    list_filter = ("servico__categoria", "servico__nome_servico")
    search_fields = ("titulo", "descricao", "servico__nome_servico")
    ordering = ("servico", "ordem")
    list_select_related = ("servico",)
    readonly_fields = ("imagem_preview",)
    fields = ("servico", "imagem", "imagem_preview", "titulo", "descricao", "ordem")
    list_per_page = 20
    autocomplete_fields = ["servico"]

    def servico_link(self, obj):
        if obj.servico:
            link = reverse("admin:servicos_servico_change", args=[obj.servico.id])
            return format_html('<a href="{}">{}</a>', link, obj.servico.nome_servico)
        return "-"

    servico_link.short_description = _("Serviço")
    servico_link.admin_order_field = "servico__nome_servico"

    def imagem_preview(self, obj):
        if obj.imagem:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 200px; max-width: 200px;" /></a>',
                obj.imagem.url,
            )
        return _("(Nenhuma imagem)")

    imagem_preview.short_description = _("Preview da Imagem")

    def imagem_preview_list(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{0}" width="60" height="60" style="object-fit: cover; border-radius: 4px;" />',
                obj.imagem.url,
            )
        return _("(Sem imagem)")

    imagem_preview_list.short_description = _("Imagem")

    def data_upload_formatada(self, obj):
        return obj.data_upload.strftime("%d/%m/%Y %H:%M") if obj.data_upload else "-"

    data_upload_formatada.short_description = _("Data Upload")
    data_upload_formatada.admin_order_field = "data_upload"

    def titulo_display(self, obj):
        return obj.titulo or _("(Sem Título)")

    titulo_display.short_description = _("Título")


@admin.register(ServicoDocumento)
class ServicoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("servico_link", "titulo", "tipo", "data_upload_formatada", "ver_arquivo")
    list_filter = ("servico__categoria", "servico__nome_servico", "tipo")
    search_fields = ("titulo", "servico__nome_servico")
    readonly_fields = ("data_upload", "filename")
    list_select_related = ("servico",)
    autocomplete_fields = ["servico"]
    fields = ("servico", "titulo", "arquivo", "filename", "tipo", "data_upload")

    def servico_link(self, obj):
        if obj.servico:
            link = reverse("admin:servicos_servico_change", args=[obj.servico.id])
            return format_html('<a href="{}">{}</a>', link, obj.servico.nome_servico)
        return "-"

    servico_link.short_description = _("Serviço")
    servico_link.admin_order_field = "servico__nome_servico"

    def ver_arquivo(self, obj):
        if obj.arquivo:
            return format_html(
                '<a href="{}" target="_blank">{} <i class="fas fa-external-link-alt fa-xs"></i></a>',
                obj.arquivo.url,
                obj.filename or _("Ver Ficheiro"),
            )
        return _("Nenhum arquivo")

    ver_arquivo.short_description = _("Ficheiro")

    def data_upload_formatada(self, obj):
        return obj.data_upload.strftime("%d/%m/%Y %H:%M") if obj.data_upload else "-"

    data_upload_formatada.short_description = _("Data Upload")
    data_upload_formatada.admin_order_field = "data_upload"


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = (
        "servico_link",
        "nome_cliente",
        "nota",
        "data_avaliacao_formatada",
        "aprovado_status",
        "comentario_resumido_list",
    )
    list_filter = ("servico__categoria__nome", "servico__nome_servico", "nota", "aprovado", "data_avaliacao")
    search_fields = ("nome_cliente", "email_cliente", "comentario", "servico__nome_servico")
    readonly_fields = ("data_avaliacao", "servico", "nome_cliente", "email_cliente", "nota", "comentario")
    actions = ["aprovar_avaliacoes", "rejeitar_avaliacoes"]
    list_select_related = ("servico",)
    list_per_page = 25
    fieldsets = (
        (
            _("Detalhes da Avaliação"),
            {"fields": ("servico", ("nome_cliente", "email_cliente"), ("nota", "data_avaliacao"))},
        ),
        (_("Conteúdo"), {"fields": ("comentario",)}),
        (_("Moderação"), {"fields": ("aprovado",)}),
    )

    def aprovar_avaliacoes(self, request, queryset):
        updated_count = queryset.update(aprovado=True)
        self.message_user(request, _(f"{updated_count} avaliações foram aprovadas."))

    aprovar_avaliacoes.short_description = _("Aprovar avaliações selecionadas")

    def rejeitar_avaliacoes(self, request, queryset):
        updated_count = queryset.update(aprovado=False)
        self.message_user(request, _(f"{updated_count} avaliações foram marcadas como não aprovadas."))

    rejeitar_avaliacoes.short_description = _("Marcar avaliações como não aprovadas")

    def servico_link(self, obj):
        if obj.servico:
            link = reverse("admin:servicos_servico_change", args=[obj.servico.id])
            return format_html('<a href="{}">{}</a>', link, obj.servico.nome_servico)
        return "-"

    servico_link.short_description = _("Serviço Avaliado")
    servico_link.admin_order_field = "servico__nome_servico"

    def aprovado_status(self, obj):
        return obj.aprovado

    aprovado_status.boolean = True
    aprovado_status.short_description = _("Aprovado")

    def data_avaliacao_formatada(self, obj):
        return obj.data_avaliacao.strftime("%d/%m/%Y %H:%M") if obj.data_avaliacao else "-"

    data_avaliacao_formatada.short_description = _("Data Avaliação")
    data_avaliacao_formatada.admin_order_field = "data_avaliacao"

    def comentario_resumido_list(self, obj):
        return (obj.comentario[:50] + "...") if obj.comentario and len(obj.comentario) > 50 else obj.comentario

    comentario_resumido_list.short_description = _("Comentário")

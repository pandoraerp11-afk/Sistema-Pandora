from django.contrib import admin

from .models import CategoriaDocumento, Documento, DocumentoVersao, RegraDocumento, TipoDocumento


@admin.register(CategoriaDocumento)
class CategoriaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "ordem")
    search_fields = ("nome",)
    list_filter = ("ativo",)
    ordering = ("ordem", "nome")


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "periodicidade", "ativo", "versionavel")
    search_fields = ("nome", "descricao")
    list_filter = ("categoria", "periodicidade", "ativo", "versionavel")
    ordering = ("categoria__ordem", "nome")


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("entidade", "tipo", "obrigatorio", "observacao")
    search_fields = ("observacao",)
    list_filter = ("tipo", "obrigatorio")


@admin.register(DocumentoVersao)
class DocumentoVersaoAdmin(admin.ModelAdmin):
    list_display = ("documento", "versao", "competencia", "status", "enviado_por", "enviado_em")
    search_fields = ("competencia", "observacao")
    list_filter = ("status", "enviado_por")
    ordering = ("-enviado_em", "-versao")


@admin.register(RegraDocumento)
class RegraDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "entidade_content_type",
        "entidade_object_id",
        "nivel_aplicacao",
        "periodicidade_override",
        "exigencia",
        "ativo",
    )
    list_filter = ("nivel_aplicacao", "exigencia", "ativo", "periodicidade_override", "tipo__categoria")
    search_fields = ("tipo__nome", "entidade_object_id")

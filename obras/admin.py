# obras/admin.py
from django.contrib import admin

from .models import DocumentoObra, Obra, Unidade


class UnidadeInline(admin.TabularInline):
    """
    Permite a edição de Unidades diretamente na página de uma Obra.
    'TabularInline' mostra os campos de forma compacta, em tabela.
    """

    model = Unidade
    # Número de formulários vazios extra para adicionar novas unidades
    extra = 1
    fields = ("identificador", "tipo_unidade", "cliente", "status", "area_m2")
    # Melhora a performance se tiver muitos clientes
    autocomplete_fields = ["cliente"]
    verbose_name = "Unidade"
    verbose_name_plural = "Unidades da Obra"


class DocumentoObraInline(admin.TabularInline):
    """
    Permite o upload de Documentos diretamente na página de uma Obra.
    """

    model = DocumentoObra
    extra = 1
    fields = ("descricao", "categoria", "arquivo")
    verbose_name = "Documento"
    verbose_name_plural = "Documentos da Obra"


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    """
    Configuração personalizada para a interface de administração do modelo Obra.
    """

    # Campos a serem exibidos na lista principal de obras
    list_display = ("nome", "cliente", "tipo_obra", "cidade", "status", "progresso")
    # Filtros que aparecerão na barra lateral direita
    list_filter = ("status", "tipo_obra", "cidade", "estado")
    # Campos que podem ser pesquisados
    search_fields = ("nome", "cliente__nome", "cno", "endereco")
    # Navegação hierárquica por data
    date_hierarchy = "data_inicio"

    # Adiciona os Inlines para Unidades e Documentos na página da Obra
    inlines = [
        UnidadeInline,
        DocumentoObraInline,
    ]

    # Organiza o formulário de edição em secções lógicas
    fieldsets = (
        ("Informações Principais", {"fields": ("nome", "tipo_obra", "cno", "status", "progresso")}),
        ("Cliente e Contrato", {"fields": ("cliente", "valor_contrato", "valor_total")}),
        ("Localização", {"fields": ("endereco", "cidade", "estado", "cep")}),
        ("Datas", {"fields": ("data_inicio", "data_previsao_termino", "data_termino")}),
        ("Observações", {"fields": ("observacoes",)}),
    )
    # Ativa um widget de busca para o campo de cliente, melhorando a performance
    autocomplete_fields = ["cliente"]

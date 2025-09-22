# servicos/urls.py
from django.urls import path

from . import views

app_name = "servicos"

urlpatterns = [
    # Dashboard
    path("home/", views.ServicoDashboardView.as_view(), name="servicos_home"),
    # URLs de Categoria
    path("categorias/", views.CategoriaServicoListView.as_view(), name="categoria_list"),
    path("categorias/nova/", views.CategoriaServicoCreateView.as_view(), name="categoria_create"),
    path("categorias/quick-create/", views.categoria_quick_create, name="categoria_create_ajax"),
    path("categorias/<slug:slug>/editar/", views.CategoriaServicoUpdateView.as_view(), name="categoria_update"),
    path("categorias/<slug:slug>/excluir/", views.CategoriaServicoDeleteView.as_view(), name="categoria_delete"),
    # URLs de Regra de Cobrança
    path("regras-cobranca/", views.RegraCobrancaListView.as_view(), name="regra_cobranca_list"),
    path("regras-cobranca/nova/", views.RegraCobrancaCreateView.as_view(), name="regra_cobranca_create"),
    path("regras-cobranca/quick-create/", views.regra_cobranca_quick_create, name="regra_cobranca_create_ajax"),
    path("unidades-medida/options/", views.unidades_medida_options, name="unidades_medida_options"),
    path("regras-cobranca/<int:pk>/editar/", views.RegraCobrancaUpdateView.as_view(), name="regra_cobranca_update"),
    path("regras-cobranca/<int:pk>/excluir/", views.RegraCobrancaDeleteView.as_view(), name="regra_cobranca_delete"),
    # URLs para Serviços Ofertados (Venda) - MAIS ESPECÍFICAS PRIMEIRO
    path("ofertados/", views.ServicoOfertadoListView.as_view(), name="servico_ofertado_list"),
    path("ofertados/novo/", views.ServicoOfertadoCreateView.as_view(), name="servico_ofertado_create"),
    path("ofertados/<slug:slug>/", views.ServicoDetailView.as_view(), name="servico_ofertado_detail"),
    path("ofertados/<slug:slug>/editar/", views.ServicoOfertadoUpdateView.as_view(), name="servico_ofertado_update"),
    path("ofertados/<slug:slug>/excluir/", views.ServicoDeleteView.as_view(), name="servico_ofertado_delete"),
    # URLs para Serviços Contratados (Compra) - MAIS ESPECÍFICAS PRIMEIRO
    path("contratados/", views.ServicoRecebidoListView.as_view(), name="servico_recebido_list"),
    path("contratados/novo/", views.ServicoRecebidoCreateView.as_view(), name="servico_recebido_create"),
    path("contratados/<slug:slug>/", views.ServicoDetailView.as_view(), name="servico_recebido_detail"),
    path("contratados/<slug:slug>/editar/", views.ServicoRecebidoUpdateView.as_view(), name="servico_recebido_update"),
    path("contratados/<slug:slug>/excluir/", views.ServicoDeleteView.as_view(), name="servico_recebido_delete"),
    # URLs para sub-recursos de Serviço (Imagens, Documentos, etc.)
    path("servico/<slug:servico_slug>/imagens/adicionar/", views.servico_imagem_add, name="servico_imagem_add"),
    path("imagens/<int:pk>/excluir/", views.servico_imagem_delete, name="servico_imagem_delete"),
    path(
        "servico/<slug:servico_slug>/documentos/adicionar/", views.servico_documento_add, name="servico_documento_add"
    ),
    path("documentos/<int:pk>/excluir/", views.servico_documento_delete, name="servico_documento_delete"),
    path("documentos/<int:pk>/download/", views.servico_documento_download, name="servico_documento_download"),
    path("servico/<slug:servico_slug>/avaliacoes/nova/", views.servico_avaliacao_add, name="servico_avaliacao_add"),
    path("avaliacoes/<int:pk>/aprovar/", views.servico_avaliacao_aprovar, name="servico_avaliacao_aprovar"),
    path(
        "avaliacoes/<int:pk>/rejeitar-excluir/",
        views.servico_avaliacao_rejeitar_ou_excluir,
        name="servico_avaliacao_rejeitar_ou_excluir",
    ),
    # API
    path(
        "api/servico/<slug:servico_slug>/calcular-preco/",
        views.calcular_preco_servico,
        name="api_calcular_preco_servico",
    ),
    # URLs adicionais referenciadas pelos templates
    path("export/", views.ServicoOfertadoListView.as_view(), name="servico_export"),  # Placeholder para export
    path(
        "duplicate/<int:pk>/", views.ServicoOfertadoCreateView.as_view(), name="servico_duplicate"
    ),  # Placeholder para duplicate
    # URLs Genéricas de Serviços (para compatibilidade com templates) - MAIS GENÉRICAS POR ÚLTIMO
    path("novo/", views.ServicoOfertadoCreateView.as_view(), name="servico_create"),
    path("<slug:slug>/editar/", views.ServicoOfertadoUpdateView.as_view(), name="servico_update"),
    path("<slug:slug>/excluir/", views.ServicoDeleteView.as_view(), name="servico_delete"),
    path("<slug:slug>/", views.ServicoDetailView.as_view(), name="servico_detail"),
    path("", views.ServicoOfertadoListView.as_view(), name="servico_list"),
]

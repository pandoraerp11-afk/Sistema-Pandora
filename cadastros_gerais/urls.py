# cadastros_gerais/urls.py
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "cadastros_gerais"

urlpatterns = [
    # Dashboard
    path("home/", views.cadastros_gerais_home, name="cadastros_gerais_home"),
    # Alias esperado pelo menu/quick access
    path("", views.cadastros_gerais_home, name="dashboard"),
    # Atalho para a raiz dos auxiliares ir para categorias
    path("auxiliares/", RedirectView.as_view(pattern_name="cadastros_gerais:categoria_aux_list", permanent=False)),
    # Ação rápida: presets
    path("presets/documentos/", views.criar_presets_documentos, name="presets_documentos"),
    # Unidades de Medida
    path("unidades-medida/", views.UnidadeMedidaListView.as_view(), name="unidade_medida_list"),
    path("unidades-medida/nova/", views.UnidadeMedidaCreateView.as_view(), name="unidade_medida_create"),
    path("unidades-medida/<int:pk>/editar/", views.UnidadeMedidaUpdateView.as_view(), name="unidade_medida_update"),
    path("unidades-medida/<int:pk>/excluir/", views.UnidadeMedidaDeleteView.as_view(), name="unidade_medida_delete"),
    path("unidades-medida/importar/", views.unidade_medida_import, name="unidade_medida_import"),
    # Categorias Auxiliares
    path("auxiliares/categorias/", views.CategoriaAuxiliarListView.as_view(), name="categoria_aux_list"),
    path("auxiliares/categorias/nova/", views.CategoriaAuxiliarCreateView.as_view(), name="categoria_aux_create"),
    path(
        "auxiliares/categorias/<int:pk>/editar/",
        views.CategoriaAuxiliarUpdateView.as_view(),
        name="categoria_aux_update",
    ),
    path(
        "auxiliares/categorias/<int:pk>/excluir/",
        views.CategoriaAuxiliarDeleteView.as_view(),
        name="categoria_aux_delete",
    ),
    # Itens Auxiliares
    path("auxiliares/itens/", views.ItemAuxiliarListView.as_view(), name="item_aux_list"),
    path("auxiliares/itens/nova/", views.ItemAuxiliarCreateView.as_view(), name="item_aux_create"),
    path("auxiliares/itens/<int:pk>/editar/", views.ItemAuxiliarUpdateView.as_view(), name="item_aux_update"),
    path("auxiliares/itens/<int:pk>/excluir/", views.ItemAuxiliarDeleteView.as_view(), name="item_aux_delete"),
]

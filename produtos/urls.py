# produtos/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .api import ProdutoAtributoDefViewSet, ProdutoAtributoValorViewSet, ProdutoBOMItemViewSet, ProdutoViewSet

app_name = "produtos"

urlpatterns = [
    # Dashboard
    path("home/", views.produtos_home, name="produtos_home"),
    # URLs principais de produtos - Class-Based Views
    path("", views.ProdutoListView.as_view(), name="produto_list"),
    path("novo/", views.ProdutoCreateView.as_view(), name="produto_create"),
    path("<int:pk>/", views.ProdutoDetailView.as_view(), name="produto_detail"),
    path("<int:pk>/editar/", views.ProdutoUpdateView.as_view(), name="produto_update"),
    path("<int:pk>/excluir/", views.ProdutoDeleteView.as_view(), name="produto_delete"),
    # URLs para categorias
    path("categorias/", views.CategoriaListView.as_view(), name="categoria_list"),
    path("categorias/nova/", views.CategoriaCreateView.as_view(), name="categoria_create"),
    path("categorias/<int:pk>/editar/", views.CategoriaUpdateView.as_view(), name="categoria_update"),
    path("categorias/<int:pk>/excluir/", views.CategoriaDeleteView.as_view(), name="categoria_delete"),
    # URLs AJAX
    path("ajax/produto/<int:pk>/toggle-ativo/", views.produto_toggle_ativo, name="produto_toggle_ativo"),
    path("ajax/produto/<int:pk>/toggle-destaque/", views.produto_toggle_destaque, name="produto_toggle_destaque"),
    path("ajax/search/", views.produtos_search_ajax, name="produtos_search_ajax"),
    # URLs para importação e exportação
    path("importar/", views.produto_import, name="produto_import"),
    path("exportar/csv/", views.produto_export_csv, name="produto_export_csv"),
    path("exportar/excel/", views.produto_export_excel, name="produto_export_excel"),
    # URLs legacy para compatibilidade (se necessário)
    path("produto_list/", views.ProdutoListView.as_view(), name="produto_list_legacy"),
    path("produto_add/", views.ProdutoCreateView.as_view(), name="produto_add"),
    path("produto_edit/<int:pk>/", views.ProdutoUpdateView.as_view(), name="produto_edit"),
    path("produto_delete/<int:pk>/", views.ProdutoDeleteView.as_view(), name="produto_delete_legacy"),
]

# API DRF moderna (prefixo opcional /api/produtos/... configurado no root urls)
router = DefaultRouter()
router.register("api/produtos", ProdutoViewSet, basename="api-produtos")
router.register("api/atributos-def", ProdutoAtributoDefViewSet, basename="api-atributos-def")
router.register("api/atributos-valores", ProdutoAtributoValorViewSet, basename="api-atributos-valores")
router.register("api/bom-itens", ProdutoBOMItemViewSet, basename="api-bom-itens")

urlpatterns += [
    path("", include(router.urls)),
]

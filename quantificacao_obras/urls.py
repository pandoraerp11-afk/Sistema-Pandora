from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnexoQuantificacaoCreateView,
    AnexoQuantificacaoDeleteView,
    AnexoQuantificacaoViewSet,
    ItemQuantificacaoCreateView,
    ItemQuantificacaoDeleteView,
    ItemQuantificacaoUpdateView,
    ItemQuantificacaoViewSet,
    ProjetoQuantificacaoCreateView,
    ProjetoQuantificacaoDeleteView,
    ProjetoQuantificacaoDetailView,
    ProjetoQuantificacaoListView,
    ProjetoQuantificacaoUpdateView,
    ProjetoQuantificacaoViewSet,
    quantificacao_obras_home,
)

app_name = "quantificacao_obras"

router = DefaultRouter()
router.register(r"projetos", ProjetoQuantificacaoViewSet)
router.register(r"itens", ItemQuantificacaoViewSet)
router.register(r"anexos", AnexoQuantificacaoViewSet)

urlpatterns = [
    # Dashboard
    path("home/", quantificacao_obras_home, name="quantificacao_obras_home"),
    # API URLs
    path("api/", include(router.urls)),
    # Template URLs - Projetos
    path("projetos/", ProjetoQuantificacaoListView.as_view(), name="projeto_list"),
    path("projetos/novo/", ProjetoQuantificacaoCreateView.as_view(), name="projeto_create"),
    path("projetos/<int:pk>/", ProjetoQuantificacaoDetailView.as_view(), name="projeto_detail"),
    path("projetos/<int:pk>/editar/", ProjetoQuantificacaoUpdateView.as_view(), name="projeto_update"),
    path("projetos/<int:pk>/excluir/", ProjetoQuantificacaoDeleteView.as_view(), name="projeto_delete"),
    # Template URLs - Itens de Quantificação (aninhadas a projetos)
    path("projetos/<int:projeto_pk>/itens/novo/", ItemQuantificacaoCreateView.as_view(), name="item_create"),
    path("projetos/<int:projeto_pk>/itens/<int:pk>/editar/", ItemQuantificacaoUpdateView.as_view(), name="item_update"),
    path(
        "projetos/<int:projeto_pk>/itens/<int:pk>/excluir/", ItemQuantificacaoDeleteView.as_view(), name="item_delete"
    ),
    # Template URLs - Anexos de Quantificação (aninhadas a projetos)
    path("projetos/<int:projeto_pk>/anexos/novo/", AnexoQuantificacaoCreateView.as_view(), name="anexo_create"),
    path(
        "projetos/<int:projeto_pk>/anexos/<int:pk>/excluir/",
        AnexoQuantificacaoDeleteView.as_view(),
        name="anexo_delete",
    ),
]

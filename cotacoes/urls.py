"""
URLs para cotações e portal fornecedor.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_portal as portal_views
from .views import AcessoFornecedorViewSet, CotacaoPublicaViewSet, CotacaoViewSet, PropostaFornecedorViewSet

app_name = "cotacoes"

# Router para APIs REST
router = DefaultRouter()
router.register(r"cotacoes", CotacaoViewSet, basename="cotacao")
router.register(r"propostas", PropostaFornecedorViewSet, basename="proposta")
router.register(r"cotacoes-publicas", CotacaoPublicaViewSet, basename="cotacao-publica")
router.register(r"acessos-fornecedor", AcessoFornecedorViewSet, basename="acesso-fornecedor")

urlpatterns = [
    # API REST
    path("api/", include(router.urls)),
    # URLs específicas para portal fornecedor
    path(
        "portal/",
        include(
            [
                # Views HTML
                path("", portal_views.portal_dashboard, name="portal-dashboard"),
                path("cotacoes/", portal_views.portal_cotacoes_list, name="portal-cotacoes"),
                path("cotacoes/<int:pk>/", portal_views.portal_cotacao_detail, name="portal-cotacao-detail"),
                path(
                    "cotacoes/<int:cotacao_id>/criar-proposta/",
                    portal_views.portal_criar_proposta,
                    name="portal-criar-proposta",
                ),
                path("propostas/", portal_views.portal_propostas_list, name="portal-propostas"),
                path("propostas/<int:pk>/", portal_views.portal_proposta_detail, name="portal-proposta-detail"),
                path("propostas/<int:pk>/editar/", portal_views.portal_proposta_edit, name="portal-proposta-edit"),
                path("propostas/<int:pk>/enviar/", portal_views.portal_enviar_proposta, name="portal-proposta-enviar"),
                # HTMX fragments / inline update
                path(
                    "propostas/<int:pk>/itens/fragment/",
                    portal_views.portal_proposta_itens_fragment,
                    name="portal-proposta-itens-fragment",
                ),
                path(
                    "propostas/<int:pk>/itens/<int:item_id>/inline-update/",
                    portal_views.portal_proposta_item_inline_update,
                    name="portal-proposta-item-inline-update",
                ),
                # Endpoints API fallback (se quiser usar listagem DRF dentro do portal)
                path("api/cotacoes/", CotacaoPublicaViewSet.as_view({"get": "list"}), name="portal-api-cotacoes"),
                path(
                    "api/cotacoes/<int:pk>/",
                    CotacaoPublicaViewSet.as_view({"get": "retrieve"}),
                    name="portal-api-cotacao-detail",
                ),
                path("api/propostas/", PropostaFornecedorViewSet.as_view({"get": "list"}), name="portal-api-propostas"),
                path(
                    "api/propostas/<int:pk>/",
                    PropostaFornecedorViewSet.as_view({"get": "retrieve"}),
                    name="portal-api-proposta-detail",
                ),
            ]
        ),
    ),
]

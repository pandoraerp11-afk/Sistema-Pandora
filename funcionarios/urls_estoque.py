# funcionarios/urls_estoque.py
# URLs para funcionalidades de controle de materiais/estoque

from django.urls import path

from . import views_estoque

app_name = "funcionarios_estoque"

urlpatterns = [
    # Dashboard
    path("dashboard/", views_estoque.dashboard_materiais, name="dashboard_materiais"),
    # Solicitações de Material
    path("solicitacoes/", views_estoque.SolicitacaoMaterialListView.as_view(), name="solicitacao_list"),
    path("solicitacoes/criar/", views_estoque.SolicitacaoMaterialCreateView.as_view(), name="solicitacao_create"),
    path("solicitacoes/<int:pk>/", views_estoque.SolicitacaoMaterialDetailView.as_view(), name="solicitacao_detail"),
    path("solicitacoes/<int:pk>/adicionar-item/", views_estoque.solicitacao_add_item, name="solicitacao_add_item"),
    path("solicitacoes/<int:pk>/aprovar/", views_estoque.aprovar_solicitacao, name="aprovar_solicitacao"),
    path("solicitacoes/<int:pk>/entregar/", views_estoque.entregar_material, name="entregar_material"),
    # ============================================================================
    # CONTROLE MANUAL DE MATERIAIS
    # ============================================================================
    # Retirada Rápida (Manual)
    path("retirada-rapida/", views_estoque.retirada_rapida, name="retirada_rapida"),
    # Devolução de Materiais
    path("devolucao/", views_estoque.devolucao_material, name="devolucao_material"),
    # Responsabilidades
    path("responsabilidades/", views_estoque.ResponsabilidadeMaterialListView.as_view(), name="responsabilidade_list"),
    # APIs/AJAX
    path("api/produtos-por-categoria/", views_estoque.produtos_por_categoria, name="produtos_por_categoria"),
    path(
        "ajax/responsabilidades/<int:funcionario_id>/",
        views_estoque.ajax_responsabilidades_funcionario,
        name="ajax_responsabilidades_funcionario",
    ),
]

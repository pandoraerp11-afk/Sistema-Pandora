# estoque/urls.py
from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    # Home principal
    path("", views.estoque_home, name="estoque_home"),
    # Itens de estoque (CRUD simplificado)
    path("itens/", views.EstoqueItemListView.as_view(), name="itens_list"),
    path("itens/<int:pk>/", views.EstoqueItemDetailView.as_view(), name="item_detail"),
    # Listagens / principais telas
    path("saldos/", views.saldos_list, name="saldos_list"),
    path("movimentos/", views.movimentos_list, name="movimentos_list"),
    path("movimentos/lista/", views.movimentos_list, name="movimento_list"),  # alias legado usado em template
    path("reservas/", views.reservas_list, name="reservas_list"),
    path("picking/", views.picking_list, name="picking_list"),
    path("picking/kanban/", views.picking_kanban, name="picking_kanban"),
    path("auditoria/", views.auditoria_list, name="auditoria_list"),
    path("depositos/", views.depositos_list, name="depositos_list"),
    # Ações
    path("movimentos/novo/", views.movimento_add, name="movimento_add"),
    path("reservas/nova/", views.reserva_add, name="reserva_add"),
    # =============================
    # CONTROLE DE MATERIAIS PARA FUNCIONÁRIOS
    # =============================
    path("materiais-funcionarios/", views.controle_materiais_funcionarios, name="controle_materiais_funcionarios"),
    path("retirada-rapida/", views.retirada_rapida_material, name="retirada_rapida_material"),
    path("devolucao-funcionario/", views.devolucao_material_funcionario, name="devolucao_material_funcionario"),
    path(
        "ajax/responsabilidades/<int:funcionario_id>/",
        views.ajax_responsabilidades_funcionario,
        name="ajax_responsabilidades_funcionario",
    ),
]

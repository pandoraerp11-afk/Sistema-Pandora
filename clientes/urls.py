"""URLs do app clientes (rotas consolidadas pós-migração do wizard/documentos).

Rotas removidas: download de documento legado (agora tratado via app 'documentos').
"""

from django.urls import path

from . import views, wizard_views

app_name = "clientes"

urlpatterns = [
    # Dashboard
    path("home/", views.clientes_home, name="clientes_home"),
    # Views principais de clientes (ListView e DetailView continuam as mesmas)
    path("", views.ClienteListView.as_view(), name="clientes_list"),
    path("<int:pk>/", views.ClienteDetailView.as_view(), name="clientes_detail"),
    # ***** WIZARD INTEGRADO *****
    # A criação e edição agora usam o WIZARD.
    # Rota canônica do Wizard (criação/edição)
    path("novo/", wizard_views.cliente_wizard_create, name="clientes_create"),
    path("<int:pk>/editar/", wizard_views.cliente_wizard_edit, name="clientes_update"),
    # Navegação direta entre steps (goto)
    path("wizard/goto/<int:step>/", wizard_views.cliente_wizard_goto_step, name="cliente_wizard_goto_step"),
    path(
        "wizard/<int:pk>/goto/<int:step>/",
        wizard_views.cliente_wizard_goto_step_edit,
        name="cliente_wizard_goto_step_edit",
    ),
    path("<int:pk>/excluir/", views.ClienteDeleteView.as_view(), name="clientes_delete"),
    # Funcionalidades especiais
    path("importar/", views.cliente_import, name="cliente_import"),
    # APIs AJAX
    path("api/search/", views.api_cliente_search, name="api_cliente_search"),
    path("api/stats/", views.api_cliente_stats, name="api_cliente_stats"),
]

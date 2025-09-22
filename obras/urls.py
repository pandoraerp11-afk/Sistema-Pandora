# obras/urls.py
from django.urls import path

from . import views
from .wizard_views import obra_wizard_create, obra_wizard_edit, obra_wizard_goto_step

app_name = "obras"

urlpatterns = [
    # Home
    path("home/", views.obras_home, name="obras_home"),
    # URLs principais para Obra (usando class-based views)
    path("", views.ObraListView.as_view(), name="obras_list"),
    # Criar/Editar agora redirecionam para o Wizard mantendo os mesmos nomes
    path("nova/", obra_wizard_create, name="obras_create"),
    path("<int:pk>/", views.ObraDetailView.as_view(), name="obra_detail"),
    path("<int:pk>/editar/", obra_wizard_edit, name="obra_edit"),
    path("<int:pk>/excluir/", views.ObraDeleteView.as_view(), name="obra_delete"),
    # URLs alternativas (function-based views para compatibilidade)
    path("list/", views.obra_list, name="obra_list"),
    path("add/", views.obra_add, name="obra_add"),
    path("<int:pk>/detail/", views.obra_detail, name="obra_detail_alt"),
    path("<int:pk>/edit/", views.obra_edit, name="obra_edit_alt"),
    path("<int:pk>/delete/", views.obra_delete, name="obra_delete_alt"),
    # URLs para Unidades
    path("<int:obra_pk>/unidades/adicionar/", views.unidade_add, name="unidade_add"),
    path("unidades/<int:pk>/excluir/", views.unidade_delete, name="unidade_delete"),
    path("<int:obra_pk>/modelos/novo/", views.modelo_unidade_create, name="modelo_unidade_create"),
    path("<int:obra_pk>/unidades/gerar/", views.gerar_unidades_em_massa, name="gerar_unidades_em_massa"),
    # URLs para Documentos
    path("documentos/<int:pk>/excluir/", views.documento_delete, name="documento_delete"),
    # URLs AJAX
    path("ajax/search/", views.obra_search_ajax, name="obra_search_ajax"),
    # Wizard (novo)
    path("wizard/", obra_wizard_create, name="obra_wizard"),
    path("wizard/<int:pk>/editar/", obra_wizard_edit, name="obra_wizard_edit"),
    path("wizard/step/<int:step>/", obra_wizard_goto_step, name="obra_wizard_goto_step"),
    path("wizard/<int:pk>/step/<int:step>/", obra_wizard_goto_step, name="obra_wizard_goto_step_edit"),
]

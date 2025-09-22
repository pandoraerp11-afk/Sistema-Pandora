# fornecedores/urls.py (VERSÃO PADRONIZADA E CORRIGIDA)
from django.urls import path

from . import views
from .wizard_views import (
    fornecedor_wizard_create,
    fornecedor_wizard_edit,
    fornecedor_wizard_entry,
    fornecedor_wizard_goto_step,
)

app_name = "fornecedores"

urlpatterns = [
    path("home/", views.fornecedores_home, name="fornecedores_home"),
    path("", views.fornecedor_list, name="fornecedores_list"),
    # Rota canônica do Wizard
    path("wizard/", fornecedor_wizard_create, name="fornecedor_wizard"),
    # Compat: 'novo/' redireciona para a rota canônica do wizard
    path("novo/", fornecedor_wizard_entry, name="fornecedor_create"),
    path("<int:pk>/", views.fornecedor_detail, name="fornecedor_detail"),
    path("<int:pk>/documentos/", views.fornecedor_documents, name="fornecedor_documents"),
    path("<int:pk>/editar/", views.fornecedor_edit, name="fornecedor_edit"),
    path("<int:pk>/excluir/", views.fornecedor_delete, name="fornecedor_delete"),
    # Rotas diretas do wizard (sem arquivo separado para evitar conflitos)
    path("wizard/<int:pk>/edit/", fornecedor_wizard_edit, name="fornecedor_wizard_edit"),
    path("wizard/step/<int:step>/", fornecedor_wizard_goto_step, name="fornecedor_wizard_goto_step"),
    path("wizard/<int:pk>/step/<int:step>/", fornecedor_wizard_goto_step, name="fornecedor_wizard_goto_step_edit"),
]

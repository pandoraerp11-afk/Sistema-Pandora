from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("", views.documento_home, name="documentos_home"),
    path("dominios/novo/ajax/", views.dominio_create_ajax, name="dominio_create_ajax"),
    # Wizard Documentos Dinâmicos
    path("wizard/docs/", views.wizard_docs_list, name="wizard_docs_list"),
    path("wizard/docs/upload/", views.wizard_docs_upload, name="wizard_docs_upload"),
    path("wizard/docs/<int:temp_id>/delete/", views.wizard_docs_delete, name="wizard_docs_delete"),
    # Setup Inteligente (bulk)
    path("setup/novo/", views.setup_inteligente, name="setup_inteligente"),
    path("setup/bulk/", views.bulk_setup_api, name="bulk_setup_api"),
    path("categorias/", views.categoria_list, name="categoria_list"),
    path("categorias/novo/", views.categoria_create, name="categoria_create"),
    path("categorias/novo/ajax/", views.categoria_create_ajax, name="categoria_create_ajax"),
    path("categorias/<int:pk>/editar/", views.categoria_edit, name="categoria_edit"),
    path("categorias/<int:pk>/excluir/", views.categoria_delete, name="categoria_delete"),
    path("categorias/reordenar/", views.categoria_reorder, name="categoria_reorder"),
    path("tipos/", views.tipo_list, name="tipo_list"),
    path("tipos/novo/", views.tipo_create, name="tipo_create"),
    path("tipos/novo/ajax/", views.tipo_create_ajax, name="tipo_create_ajax"),
    path("tipos/<int:pk>/editar/", views.tipo_edit, name="tipo_edit"),
    # Regras AJAX
    path("regras/novo/ajax/", views.regra_create_ajax, name="regra_create_ajax"),
    path("regras/<int:regra_id>/transition/", views.regra_transition_ajax, name="regra_transition_ajax"),
    path("entidade/<str:app_label>/<int:object_id>/documentos/", views.documento_list, name="documento_list"),
    path("entidade/<str:app_label>/<int:object_id>/documentos/novo/", views.documento_create, name="documento_create"),
    path("documento/<int:pk>/versoes/", views.versao_list, name="versao_list"),
    path("documento/<int:pk>/versoes/novo/", views.versao_create, name="versao_create"),
    # Criar regra global (a partir da home)
    path("regras/nova/", views.regra_create_global, name="regra_create_global"),
    # Regras por entidade
    path("entidade/<str:app_label>/<int:object_id>/regras/", views.regra_list, name="regra_list"),
    path("entidade/<str:app_label>/<int:object_id>/regras/nova/", views.regra_create, name="regra_create"),
    path("regras/<int:pk>/editar/", views.regra_edit, name="regra_edit"),
    path("regras/<int:pk>/excluir/", views.regra_delete, name="regra_delete"),
]

from django.urls import path

from . import views

app_name = "formularios_dinamicos"

urlpatterns = [
    # Dashboard
    path("home/", views.formularios_dinamicos_home, name="formularios_dinamicos_home"),
    # Formulários
    path("", views.form_list, name="form_list"),
    path("criar/", views.form_create, name="form_create"),
    path("<int:pk>/", views.form_detail, name="form_detail"),
    path("<int:pk>/editar/", views.form_update, name="form_update"),
    # Campos
    path("<int:form_pk>/campos/criar/", views.campo_create, name="campo_create"),
    path("<int:form_pk>/campos/<int:campo_pk>/editar/", views.campo_update, name="campo_update"),
    path("<int:form_pk>/campos/<int:campo_pk>/excluir/", views.campo_delete, name="campo_delete"),
    # Renderização e respostas
    path("f/<slug:slug>/", views.form_render, name="form_render"),
    path("f/<slug:form_slug>/resposta/<uuid:token>/", views.resposta_detail, name="resposta_detail"),
    # Gerenciamento de respostas
    path("<int:form_pk>/respostas/", views.resposta_list, name="resposta_list"),
    path(
        "<int:form_pk>/respostas/<int:resposta_pk>/status/", views.resposta_update_status, name="resposta_update_status"
    ),
    # Templates
    path("templates/", views.template_list, name="template_list"),
    path("templates/<int:template_pk>/usar/", views.form_from_template, name="form_from_template"),
    # APIs
    path("api/<int:pk>/stats/", views.api_form_stats, name="api_form_stats"),
    path("api/<int:form_pk>/campos/reordenar/", views.api_campo_reorder, name="api_campo_reorder"),
]

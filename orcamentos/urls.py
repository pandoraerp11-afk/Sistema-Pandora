# orcamentos/urls.py
from django.urls import path

from . import views  # CORRIGIDO

app_name = "orcamentos"

urlpatterns = [
    # Dashboard
    path("home/", views.orcamentos_home, name="orcamentos_home"),
    # Lista (singular e plural alias)
    path("", views.OrcamentosListView.as_view(), name="orcamento_list"),
    path("lista/", views.OrcamentosListView.as_view(), name="orcamentos_list"),
    # CRUD
    path("<int:pk>/", views.OrcamentosDetailView.as_view(), name="orcamento_detail"),
    path("novo/", views.OrcamentosCreateView.as_view(), name="orcamento_create"),
    path("novo/novo/", views.OrcamentosCreateView.as_view(), name="orcamentos_create"),
    path("<int:pk>/editar/", views.OrcamentosUpdateView.as_view(), name="orcamento_update"),
    path("<int:pk>/editar/editar/", views.OrcamentosUpdateView.as_view(), name="orcamentos_update"),
    path("<int:pk>/excluir/", views.OrcamentosDeleteView.as_view(), name="orcamento_delete"),
    path("<int:pk>/excluir/excluir/", views.OrcamentosDeleteView.as_view(), name="orcamentos_delete"),
]

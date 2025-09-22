# treinamento/urls.py
from django.urls import path

from . import views  # CORRIGIDO (era from .treinamento import views)

app_name = "treinamento"

urlpatterns = [
    # Dashboard
    path("home/", views.treinamento_home, name="treinamento_home"),
    path("", views.TreinamentoListView.as_view(), name="treinamentos_list"),  # Corrigido para corresponder ao menu
    path("<int:pk>/", views.TreinamentoDetailView.as_view(), name="treinamento_detail"),
    path("novo/", views.TreinamentoCreateView.as_view(), name="treinamento_create"),
    path("<int:pk>/editar/", views.TreinamentoUpdateView.as_view(), name="treinamento_update"),
    path("<int:pk>/excluir/", views.TreinamentoDeleteView.as_view(), name="treinamento_delete"),
]

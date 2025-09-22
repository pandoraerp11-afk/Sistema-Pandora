# aprovacoes/urls.py
from django.urls import path

from . import views

app_name = "aprovacoes"

urlpatterns = [
    # Dashboard
    path("home/", views.aprovacoes_home, name="aprovacoes_home"),
    path("", views.AprovacoesListView.as_view(), name="aprovacoes_list"),
    path("<int:pk>/", views.AprovacoesDetailView.as_view(), name="aprovacoes_detail"),
    path("novo/", views.AprovacoesCreateView.as_view(), name="aprovacoes_create"),
    path("<int:pk>/editar/", views.AprovacoesUpdateView.as_view(), name="aprovacoes_update"),
    path("<int:pk>/excluir/", views.AprovacoesDeleteView.as_view(), name="aprovacoes_delete"),
    # URLs AJAX
    path("<int:pk>/aprovar/", views.aprovar_aprovacao, name="aprovar_aprovacao"),
    path("<int:pk>/rejeitar/", views.rejeitar_aprovacao, name="rejeitar_aprovacao"),
]

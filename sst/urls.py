# sst/urls.py
from django.urls import path

from . import views  # CORRIGIDO (era from .sst import views)

app_name = "sst"

urlpatterns = [
    # Dashboard home
    path("", views.sst_home, name="sst_home"),
    # Lista (mantida para navegação / ações rápidas)
    path("lista/", views.SstListView.as_view(), name="sst_list"),
    path("<int:pk>/", views.SstDetailView.as_view(), name="sst_detail"),
    path("novo/", views.SstCreateView.as_view(), name="sst_create"),
    path("<int:pk>/editar/", views.SstUpdateView.as_view(), name="sst_update"),
    path("<int:pk>/excluir/", views.SstDeleteView.as_view(), name="sst_delete"),
]

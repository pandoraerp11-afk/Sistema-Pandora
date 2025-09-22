# relatorios/urls.py
from django.urls import path

from . import views  # CORRIGIDO (era from .relatorios import views)

app_name = "relatorios"

urlpatterns = [
    # Dashboard
    path("home/", views.relatorios_home, name="relatorios_home"),
    path("", views.RelatoriosListView.as_view(), name="relatorios_list"),
    path("<int:pk>/", views.RelatoriosDetailView.as_view(), name="relatorios_detail"),
    path("novo/", views.RelatoriosCreateView.as_view(), name="relatorios_create"),
    path("<int:pk>/editar/", views.RelatoriosUpdateView.as_view(), name="relatorios_update"),
    path("<int:pk>/excluir/", views.RelatoriosDeleteView.as_view(), name="relatorios_delete"),
]

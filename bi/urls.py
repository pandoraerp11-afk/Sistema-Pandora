# bi/urls.py
from django.urls import path

from . import views

app_name = "bi"

urlpatterns = [
    path("home/", views.dashboard_view, name="bi_home"),
    path("", views.BiListView.as_view(), name="bi_list"),
    path("reports/", views.dashboard_view, name="bi_reports"),
    path("<int:pk>/", views.BiDetailView.as_view(), name="bi_detail"),
    path("novo/", views.BiCreateView.as_view(), name="bi_create"),
    path("<int:pk>/editar/", views.BiUpdateView.as_view(), name="bi_update"),
    path("<int:pk>/excluir/", views.BiDeleteView.as_view(), name="bi_delete"),
    # API URLs
    path("api/stats/", views.api_indicador_stats, name="api_indicador_stats"),
]

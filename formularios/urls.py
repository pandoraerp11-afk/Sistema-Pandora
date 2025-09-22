# formularios/urls.py
from django.urls import path

from . import views  # CORRIGIDO (era from .formularios import views)

app_name = "formularios"

urlpatterns = [
    # Dashboard
    path("home/", views.formularios_home, name="formularios_home"),
    path("", views.FormulariosListView.as_view(), name="formulario_list"),
    path("<int:pk>/", views.FormulariosDetailView.as_view(), name="formularios_detail"),
    path("novo/", views.FormulariosCreateView.as_view(), name="formularios_create"),
    path("<int:pk>/editar/", views.FormulariosUpdateView.as_view(), name="formularios_update"),
    path("<int:pk>/excluir/", views.FormulariosDeleteView.as_view(), name="formularios_delete"),
]

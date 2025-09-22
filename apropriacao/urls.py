# apropriacao/urls.py
from django.urls import path

from . import views  # CORRIGIDO (era from .apropriacao import views)

app_name = "apropriacao"

urlpatterns = [
    # Dashboard
    path("home/", views.apropriacao_home, name="apropriacao_home"),
    path("", views.ApropriacaoListView.as_view(), name="apropriacao_list"),
    path("<int:pk>/", views.ApropriacaoDetailView.as_view(), name="apropriacao_detail"),
    path("novo/", views.ApropriacaoCreateView.as_view(), name="apropriacao_create"),
    path("<int:pk>/editar/", views.ApropriacaoUpdateView.as_view(), name="apropriacao_update"),
    path("<int:pk>/excluir/", views.ApropriacaoDeleteView.as_view(), name="apropriacao_delete"),
]

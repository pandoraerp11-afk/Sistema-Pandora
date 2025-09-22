# mao_obra/urls.py
from django.urls import path

from . import views

app_name = "mao_obra"

urlpatterns = [
    # Dashboard
    path("home/", views.mao_obra_home, name="mao_obra_home"),
    # CRUD básico
    path("", views.MaoObraListView.as_view(), name="mao_obra_list"),
    path("<int:pk>/", views.MaoObraDetailView.as_view(), name="mao_obra_detail"),
    path("novo/", views.MaoObraCreateView.as_view(), name="mao_obra_create"),
    path("<int:pk>/editar/", views.MaoObraUpdateView.as_view(), name="mao_obra_update"),
    path("<int:pk>/excluir/", views.MaoObraDeleteView.as_view(), name="mao_obra_delete"),
    # URLs utilitárias
    path("ajax/search/", views.mao_obra_search_ajax, name="mao_obra_search_ajax"),
    path(
        "relatorio/funcionario/<int:funcionario_pk>/",
        views.relatorio_mao_obra_funcionario,
        name="relatorio_funcionario",
    ),
    path("relatorio/obra/<int:obra_pk>/", views.relatorio_mao_obra_obra, name="relatorio_obra"),
]

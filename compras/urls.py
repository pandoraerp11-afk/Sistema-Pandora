# compras/urls.py
from django.urls import path

from . import views  # Garante que está importando o views.py com as FUNÇÕES

app_name = "compras"  # Define o namespace 'compras'

urlpatterns = [
    # Dashboard
    path("home/", views.compras_home, name="compras_home"),
    # Para a lista de compras
    path("", views.compra_list, name="compras_list"),
    # Para o detalhe da compra
    path("<int:pk>/", views.compra_detail, name="compra_detail"),
    # Para adicionar nova compra
    path("novo/", views.compra_add, name="compras_create"),
    # Para editar compra
    path("<int:pk>/editar/", views.compra_edit, name="compra_edit"),
    # Para excluir compra
    path("<int:pk>/excluir/", views.compra_delete, name="compra_delete"),
    # NOVA ROTA ADICIONADA ABAIXO:
    path("cotacoes/", views.cotacoes_list, name="cotacoes_list"),
]

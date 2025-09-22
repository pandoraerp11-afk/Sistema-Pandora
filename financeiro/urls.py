from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    # Dashboard
    path("home/", views.financeiro_home, name="financeiro_home"),
    path("", views.financeiro_list, name="financeiro_list"),
    path("<int:pk>/", views.financeiro_detail, name="financeiro_detail"),
    path("novo/", views.financeiro_add, name="financeiro_add"),
    path("<int:pk>/editar/", views.financeiro_edit, name="financeiro_edit"),
    path("<int:pk>/excluir/", views.financeiro_delete, name="financeiro_delete"),
    # Contas a Pagar
    path("contas-pagar/", views.conta_pagar_list, name="conta_pagar_list"),
    path("contas-pagar/novo/", views.conta_pagar_add, name="conta_pagar_add"),
    path("contas-pagar/<int:pk>/", views.conta_pagar_detail, name="conta_pagar_detail"),
    path("contas-pagar/<int:pk>/editar/", views.conta_pagar_edit, name="conta_pagar_edit"),
    path("contas-pagar/<int:pk>/excluir/", views.conta_pagar_delete, name="conta_pagar_delete"),
    path("contas-pagar/<int:pk>/pagar/", views.conta_pagar_pagar, name="conta_pagar_pagar"),
    # Contas a Receber
    path("contas-receber/", views.conta_receber_list, name="conta_receber_list"),
    path("contas-receber/novo/", views.conta_receber_add, name="conta_receber_add"),
    path("contas-receber/<int:pk>/", views.conta_receber_detail, name="conta_receber_detail"),
    path("contas-receber/<int:pk>/editar/", views.conta_receber_edit, name="conta_receber_edit"),
    path("contas-receber/<int:pk>/excluir/", views.conta_receber_delete, name="conta_receber_delete"),
    path("contas-receber/<int:pk>/receber/", views.conta_receber_receber, name="conta_receber_receber"),
]

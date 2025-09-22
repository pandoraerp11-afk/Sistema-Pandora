from django.urls import path

from . import views

app_name = "assistente_web"

urlpatterns = [
    path("", views.assistente_home, name="home"),
    path("processar/", views.processar_comando, name="processar_comando"),
    path("nova-conversa/", views.nova_conversa, name="nova_conversa"),
    path("conversa/<int:conversa_id>/", views.obter_conversa, name="obter_conversa"),
    path("configuracoes/", views.configuracoes, name="configuracoes"),
    path("historico/", views.historico_conversas, name="historico"),
]

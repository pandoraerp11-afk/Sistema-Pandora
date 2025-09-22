from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    # Dashboard
    path("home/", views.chat_home, name="chat_home"),
    # Views principais de conversas
    path("", views.ConversaListView.as_view(), name="chat_view"),
    path("conversas/", views.ConversaListView.as_view(), name="conversa_list"),
    path("conversas/nova/", views.ConversaCreateView.as_view(), name="conversa_create"),
    path("conversas/<int:pk>/", views.ConversaDetailView.as_view(), name="conversa_detail"),
    path("conversas/<int:pk>/editar/", views.ConversaUpdateView.as_view(), name="conversa_update"),
    path("conversas/<int:pk>/excluir/", views.ConversaDeleteView.as_view(), name="conversa_delete"),
    # Views de mensagens
    path("conversas/<int:conversa_id>/mensagem/", views.MensagemCreateView.as_view(), name="mensagem_create"),
    # Configurações
    path("configuracoes/", views.configuracao_chat_view, name="configuracao_chat"),
    path("preferencias/", views.preferencia_usuario_view, name="preferencia_usuario"),
    # APIs AJAX
    path("api/enviar-mensagem/", views.api_enviar_mensagem, name="api_enviar_mensagem"),
    path("api/marcar-como-lida/", views.api_marcar_como_lida, name="api_marcar_como_lida"),
    path("api/conversas-recentes/", views.api_conversas_recentes, name="api_conversas_recentes"),
    path("api/contacts/", views.api_contacts, name="api_contacts"),
    path("api/start/", views.api_start_conversa, name="api_start_conversa"),
    path("api/conversa/<int:conversa_id>/mensagens/", views.api_conversa_mensagens, name="api_conversa_mensagens"),
    path("api/upload/", views.api_upload_arquivo, name="api_upload_arquivo"),
    path("api/favorito/toggle/", views.api_toggle_favorito, name="api_toggle_favorito"),
    path("api/mensagem/reagir/", views.api_reagir_mensagem, name="api_reagir_mensagem"),
    path("api/mensagem/fixar/", views.api_fixar_mensagem, name="api_fixar_mensagem"),
    # Compatibilidade com URLs antigas
    path("chat_detail/<int:pk>/", views.ConversaDetailView.as_view(), name="chat_detail"),
]

# agenda/urls.py
from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    # Dashboard
    path("home/", views.agenda_home, name="agenda_home"),
    # URLs principais para Evento (usando class-based views)
    path("", views.EventoListView.as_view(), name="evento_list"),
    path("eventos/", views.EventoListView.as_view(), name="eventos_list"),
    path("evento/novo/", views.EventoCreateView.as_view(), name="evento_create"),
    path("evento/<int:pk>/", views.EventoDetailView.as_view(), name="evento_detail"),
    path("evento/<int:pk>/editar/", views.EventoUpdateView.as_view(), name="evento_update"),
    path("evento/<int:pk>/excluir/", views.EventoDeleteView.as_view(), name="evento_delete"),
    path("evento/<int:pk>/lembretes/", views.gerenciar_lembrete_participante, name="evento_lembretes_gerenciar"),
    # Calendário
    path("calendario/", views.agenda_calendar, name="agenda_calendar"),
    path("calendar/", views.agenda_calendar, name="agenda_calendar_alt"),
    # URLs AJAX
    path("ajax/evento/criar/", views.evento_ajax_create, name="evento_ajax_create"),
    path("ajax/evento/<int:pk>/status/", views.evento_ajax_update_status, name="evento_ajax_update_status"),
    path("ajax/evento/buscar/", views.evento_search_ajax, name="evento_search_ajax"),
    path("api/eventos/", views.api_eventos, name="api_eventos"),
    # Relatórios
    path("relatorios/eventos/", views.eventos_relatorio, name="eventos_relatorio"),
    # URLs alternativas (function-based views para compatibilidade)
    path("list/", views.evento_list, name="evento_list_alt"),
    path("add/", views.evento_add, name="evento_add"),
    path("<int:pk>/detail/", views.evento_detail, name="evento_detail_alt"),
    path("<int:pk>/edit/", views.evento_edit, name="evento_edit"),
    path("<int:pk>/delete/", views.evento_delete, name="evento_delete_alt"),
]

from django.urls import include, path
from rest_framework import routers

from . import views
from .api_views import (
    AgendamentoV2ViewSet,
    AgendamentoViewSet,
    AuditoriaAgendamentoViewSet,
    ClienteAgendamentoViewSet,
    ClienteSlotViewSet,
    DisponibilidadeViewSet,
    SlotViewSet,
)

router = routers.DefaultRouter()
router.register(r"disponibilidades", DisponibilidadeViewSet, basename="disponibilidade")
router.register(r"slots", SlotViewSet, basename="slot")
router.register(r"agendamentos", AgendamentoViewSet, basename="agendamento")
router.register(r"v2/agendamentos", AgendamentoV2ViewSet, basename="agendamento-v2")
# Ajuste de rota conforme documentação (/api/agendamentos/auditoria/)
router.register(r"agendamentos/auditoria", AuditoriaAgendamentoViewSet, basename="agendamento-auditoria")

# Rotas do Portal do Cliente
cliente_router = routers.DefaultRouter()
cliente_router.register(r"slots", ClienteSlotViewSet, basename="cliente-slot")
cliente_router.register(r"agendamentos", ClienteAgendamentoViewSet, basename="cliente-agendamento")

app_name = "agendamentos"
urlpatterns = [
    path("api/", include(router.urls)),
    path("api/cliente/", include(cliente_router.urls)),
    path("", views.agendamento_home_view, name="home"),
    # HTML Views
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("agendamentos/", views.AgendamentoListView.as_view(), name="agendamento-list"),
    path("agendamentos/novo/", views.AgendamentoCreateView.as_view(), name="agendamento-create"),
    path("agendamentos/<int:pk>/", views.AgendamentoDetailView.as_view(), name="agendamento-detail"),
    path("agendamentos/<int:pk>/editar/", views.AgendamentoUpdateView.as_view(), name="agendamento-edit"),
    path("agendamentos/<int:pk>/<str:acao>/", views.agendamento_action_view, name="agendamento-action"),
    path("slots/", views.SlotListView.as_view(), name="slot-list"),
    path("slots/<int:pk>/", views.SlotDetailView.as_view(), name="slot-detail"),
    path("slots/gerar/", views.gerar_slots_view, name="slot-gerar"),
    path("waitlist/<int:slot_id>/inscrever/", views.waitlist_inscrever_view, name="waitlist-inscrever"),
    # Disponibilidades
    path("disponibilidades/", views.DisponibilidadeListView.as_view(), name="disponibilidade-list"),
    path("disponibilidades/nova/", views.DisponibilidadeCreateView.as_view(), name="disponibilidade-create"),
    path("disponibilidades/<int:pk>/", views.DisponibilidadeDetailView.as_view(), name="disponibilidade-detail"),
    path("disponibilidades/<int:pk>/editar/", views.DisponibilidadeUpdateView.as_view(), name="disponibilidade-edit"),
    # Auditoria
    path("auditoria/", views.AuditoriaListView.as_view(), name="auditoria-list"),
    # Reagendar
    path("agendamentos/<int:pk>/reagendar/", views.reagendar_view, name="agendamento-reagendar"),
    # Waitlist global
    path("waitlist/", views.WaitlistListView.as_view(), name="waitlist-list"),
    # --- Rotas com sufixo -ui (nova convenção) ---
    path("ui/dashboard/", views.dashboard_view, name="dashboard-ui"),
    path("ui/agendamentos/", views.AgendamentoListView.as_view(), name="agendamento-list-ui"),
    path("ui/agendamentos/novo/", views.AgendamentoCreateView.as_view(), name="agendamento-create-ui"),
    path("ui/agendamentos/<int:pk>/", views.AgendamentoDetailView.as_view(), name="agendamento-detail-ui"),
    path("ui/agendamentos/<int:pk>/editar/", views.AgendamentoUpdateView.as_view(), name="agendamento-edit-ui"),
    path("ui/agendamentos/<int:pk>/<str:acao>/", views.agendamento_action_view, name="agendamento-action-ui"),
    path("ui/slots/", views.SlotListView.as_view(), name="slot-list-ui"),
    path("ui/slots/<int:pk>/", views.SlotDetailView.as_view(), name="slot-detail-ui"),
    path("ui/slots/gerar/", views.gerar_slots_view, name="slot-gerar-ui"),
    path("ui/disponibilidades/", views.DisponibilidadeListView.as_view(), name="disponibilidade-list-ui"),
    path("ui/disponibilidades/nova/", views.DisponibilidadeCreateView.as_view(), name="disponibilidade-create-ui"),
    path("ui/disponibilidades/<int:pk>/", views.DisponibilidadeDetailView.as_view(), name="disponibilidade-detail-ui"),
    path(
        "ui/disponibilidades/<int:pk>/editar/",
        views.DisponibilidadeUpdateView.as_view(),
        name="disponibilidade-edit-ui",
    ),
    path("ui/auditoria/", views.AuditoriaListView.as_view(), name="auditoria-list-ui"),
    path("ui/agendamentos/<int:pk>/reagendar/", views.reagendar_view, name="agendamento-reagendar-ui"),
    path("ui/waitlist/", views.WaitlistListView.as_view(), name="waitlist-list-ui"),
]

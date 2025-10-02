"""Rotas do app portal_cliente (inclui views portal e endpoints AJAX Fase 2)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_portal
from .views import ContaClienteViewSet, DocumentoPortalClienteViewSet

app_name = "portal_cliente"
router = DefaultRouter()
router.register("contas", ContaClienteViewSet, basename="conta-cliente")
router.register("documentos", DocumentoPortalClienteViewSet, basename="doc-portal-cliente")

urlpatterns = [
    path("api/", include(router.urls)),
    path(
        "portal/",
        include(
            [
                # Dashboard principal
                path("", views_portal.dashboard, name="dashboard"),
                path("documentos/", views_portal.documentos_list, name="documentos"),
                # Agendamentos - Fase 1
                path("agendamentos/", views_portal.agendamentos_lista, name="agendamentos_lista"),
                path("agendamentos/novo/", views_portal.novo_agendamento, name="novo_agendamento"),
                path(
                    "agendamentos/<int:agendamento_id>/cancelar/",
                    views_portal.cancelar_agendamento,
                    name="cancelar_agendamento",
                ),
                # Histórico de Atendimentos - Fase 1
                path("historico/", views_portal.historico_atendimentos, name="historico_atendimentos"),
                path("historico/<int:atendimento_id>/", views_portal.detalhe_atendimento, name="detalhe_atendimento"),
                # Galeria de Fotos - Fase 1
                path("galeria/", views_portal.galeria_fotos, name="galeria_fotos"),
                path("galeria/<int:foto_id>/", views_portal.visualizar_foto, name="visualizar_foto"),
                # AJAX endpoints para interface dinâmica
                path("ajax/slots-disponiveis/", views_portal.slots_disponiveis_ajax, name="slots_disponiveis_ajax"),
                path("ajax/servicos/", views_portal.servicos_ajax, name="servicos_ajax"),
                path("ajax/profissionais/", views_portal.profissionais_ajax, name="profissionais_ajax"),
                path(
                    "ajax/agendamento/criar/",
                    views_portal.criar_agendamento_ajax,
                    name="criar_agendamento_ajax",
                ),
                path(
                    "ajax/agendamento/<int:agendamento_id>/cancelar-ajax/",
                    views_portal.cancelar_agendamento_ajax,
                    name="cancelar_agendamento_ajax",
                ),
                path(
                    "ajax/agendamento/<int:agendamento_id>/status/",
                    views_portal.agendamento_status_ajax,
                    name="agendamento_status_ajax",
                ),
                # Fase 2 - novos endpoints AJAX
                path(
                    "ajax/agendamento/<int:agendamento_id>/checkin/",
                    views_portal.checkin_agendamento_ajax,
                    name="checkin_agendamento_ajax",
                ),
                path(
                    "ajax/atendimento/<int:atendimento_id>/finalizar/",
                    views_portal.finalizar_atendimento_ajax,
                    name="finalizar_atendimento_ajax",
                ),
                path(
                    "ajax/atendimento/<int:atendimento_id>/avaliar/",
                    views_portal.avaliar_atendimento_ajax,
                    name="avaliar_atendimento_ajax",
                ),
            ],
        ),
    ),
]

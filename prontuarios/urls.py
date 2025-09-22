from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    AnamneseViewSet,
    AtendimentoViewSet,
    FotoEvolucaoViewSet,
    PerfilClinicoViewSet,
    search_clientes,
    search_profissionais,
    upload_foto_evolucao_mobile,
)
from .views import (
    AnamneseCreateView,
    AnamneseDeleteView,
    AnamneseDetailView,
    AnamneseListView,
    AnamneseUpdateView,
    AtendimentoCreateView,
    AtendimentoDeleteView,
    AtendimentoDetailView,
    AtendimentoListView,
    AtendimentoUpdateView,
    FotoEvolucaoCreateView,
    FotoEvolucaoDeleteView,
    FotoEvolucaoDetailView,
    FotoEvolucaoListView,
    FotoEvolucaoUpdateView,
    PerfilClinicoCreateView,
    PerfilClinicoDeleteView,
    PerfilClinicoDetailView,
    PerfilClinicoListView,
    PerfilClinicoUpdateView,
    prontuarios_home,
)

app_name = "prontuarios"

router = DefaultRouter()
router.register(r"atendimentos", AtendimentoViewSet)
router.register(r"fotos-evolucao", FotoEvolucaoViewSet)
router.register(r"anamneses", AnamneseViewSet)
router.register(r"perfis-clinicos", PerfilClinicoViewSet)
# slots/disponibilidades removidos do módulo Prontuários (agenda unificada no módulo Agendamentos)

urlpatterns = [
    # === Dashboard / Home unificada ===
    path("", prontuarios_home, name="index"),
    path("", prontuarios_home, name="prontuario_index"),  # legacy alias
    path("home/", prontuarios_home, name="home"),
    path("dashboard/", prontuarios_home, name="dashboard"),  # alias mais claro
    path("home/", prontuarios_home, name="prontuarios_home"),  # legacy
    # (URLs legacy de paciente removidas – fase final da migração)
    # Procedimentos removidos – usar módulo servicos
    # === Atendimentos ===
    path("atendimentos/", AtendimentoListView.as_view(), name="atendimentos_list"),
    path("atendimentos/", AtendimentoListView.as_view(), name="atendimento_list"),  # legacy
    path("atendimentos/novo/", AtendimentoCreateView.as_view(), name="atendimentos_create"),
    path("atendimentos/novo/", AtendimentoCreateView.as_view(), name="atendimento_create"),  # legacy
    path("atendimentos/<int:pk>/", AtendimentoDetailView.as_view(), name="atendimentos_detail"),
    path("atendimentos/<int:pk>/", AtendimentoDetailView.as_view(), name="atendimento_detail"),  # legacy
    path("atendimentos/<int:pk>/editar/", AtendimentoUpdateView.as_view(), name="atendimentos_update"),
    path("atendimentos/<int:pk>/editar/", AtendimentoUpdateView.as_view(), name="atendimento_update"),  # legacy
    path("atendimentos/<int:pk>/excluir/", AtendimentoDeleteView.as_view(), name="atendimentos_delete"),
    path("atendimentos/<int:pk>/excluir/", AtendimentoDeleteView.as_view(), name="atendimento_delete"),  # legacy
    # === Fotos de Evolução ===
    path("fotos-evolucao/", FotoEvolucaoListView.as_view(), name="fotos_evolucao_list"),
    path("fotos-evolucao/", FotoEvolucaoListView.as_view(), name="fotoevolucao_list"),  # legacy
    path("fotos-evolucao/novo/", FotoEvolucaoCreateView.as_view(), name="fotos_evolucao_create"),
    path("fotos-evolucao/novo/", FotoEvolucaoCreateView.as_view(), name="fotoevolucao_create"),  # legacy
    path("fotos-evolucao/<int:pk>/", FotoEvolucaoDetailView.as_view(), name="fotos_evolucao_detail"),
    path("fotos-evolucao/<int:pk>/", FotoEvolucaoDetailView.as_view(), name="fotoevolucao_detail"),  # legacy
    path("fotos-evolucao/<int:pk>/editar/", FotoEvolucaoUpdateView.as_view(), name="fotos_evolucao_update"),
    path("fotos-evolucao/<int:pk>/editar/", FotoEvolucaoUpdateView.as_view(), name="fotoevolucao_update"),  # legacy
    path("fotos-evolucao/<int:pk>/excluir/", FotoEvolucaoDeleteView.as_view(), name="fotos_evolucao_delete"),
    path("fotos-evolucao/<int:pk>/excluir/", FotoEvolucaoDeleteView.as_view(), name="fotoevolucao_delete"),  # legacy
    # === Anamneses === (templates ainda serão criados na Fase 0)
    path("anamneses/", AnamneseListView.as_view(), name="anamneses_list"),
    path("anamneses/", AnamneseListView.as_view(), name="anamnese_list"),  # legacy
    path("anamneses/novo/", AnamneseCreateView.as_view(), name="anamneses_create"),
    path("anamneses/novo/", AnamneseCreateView.as_view(), name="anamnese_create"),  # legacy
    path("anamneses/<int:pk>/", AnamneseDetailView.as_view(), name="anamneses_detail"),
    path("anamneses/<int:pk>/", AnamneseDetailView.as_view(), name="anamnese_detail"),  # legacy
    path("anamneses/<int:pk>/editar/", AnamneseUpdateView.as_view(), name="anamneses_update"),
    path("anamneses/<int:pk>/editar/", AnamneseUpdateView.as_view(), name="anamnese_update"),  # legacy
    path("anamneses/<int:pk>/excluir/", AnamneseDeleteView.as_view(), name="anamneses_delete"),
    path("anamneses/<int:pk>/excluir/", AnamneseDeleteView.as_view(), name="anamnese_delete"),  # legacy
    # === Perfis Clínicos ===
    path("perfis-clinicos/", PerfilClinicoListView.as_view(), name="perfils_clinicos_list"),
    path("perfis-clinicos/", PerfilClinicoListView.as_view(), name="perfilclinico_list"),  # legacy
    path("perfis-clinicos/novo/", PerfilClinicoCreateView.as_view(), name="perfils_clinicos_create"),
    path("perfis-clinicos/novo/", PerfilClinicoCreateView.as_view(), name="perfilclinico_create"),  # legacy
    path("perfis-clinicos/<int:pk>/", PerfilClinicoDetailView.as_view(), name="perfils_clinicos_detail"),
    path("perfis-clinicos/<int:pk>/", PerfilClinicoDetailView.as_view(), name="perfilclinico_detail"),  # legacy
    path("perfis-clinicos/<int:pk>/editar/", PerfilClinicoUpdateView.as_view(), name="perfils_clinicos_update"),
    path("perfis-clinicos/<int:pk>/editar/", PerfilClinicoUpdateView.as_view(), name="perfilclinico_update"),  # legacy
    path("perfis-clinicos/<int:pk>/excluir/", PerfilClinicoDeleteView.as_view(), name="perfils_clinicos_delete"),
    path("perfis-clinicos/<int:pk>/excluir/", PerfilClinicoDeleteView.as_view(), name="perfilclinico_delete"),  # legacy
    # === Disponibilidades & Slots === (removidos deste módulo)
    # === Quick-Create (Ajax) ===
    # quick-create removido (usar criação de serviço clínico em servicos)
    path("api/mobile/upload-foto/", upload_foto_evolucao_mobile, name="upload_foto_evolucao_mobile"),
    # === Buscas Select2 ===
    path("api/search/clientes/", search_clientes, name="search_clientes"),
    path("api/search/profissionais/", search_profissionais, name="search_profissionais"),
    # === API (mantido em /prontuarios/api/...) ===
    path("api/", include(router.urls)),
]

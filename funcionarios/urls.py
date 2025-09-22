# funcionarios/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, wizard_views
from .api import BeneficioViewSet, CartaoPontoViewSet, FeriasViewSet, FuncionarioViewSet

router = DefaultRouter()
router.register(r"funcionarios", FuncionarioViewSet)
router.register(r"ferias", FeriasViewSet)
router.register(r"ponto", CartaoPontoViewSet)
router.register(r"beneficios", BeneficioViewSet)

app_name = "funcionarios"

urlpatterns = [
    # Dashboard
    path("home/", views.funcionarios_home, name="funcionarios_home"),
    # URLs principais de funcionários
    path("", views.FuncionarioListView.as_view(), name="funcionario_list"),
    # Rota legada de adicionar agora aponta para o wizard (backward compatibility)
    path("adicionar/", wizard_views.funcionario_wizard_create, name="funcionario_create"),
    # Wizard novo
    path("novo/", wizard_views.funcionario_wizard_create, name="funcionario_wizard_create"),
    path("wizard/goto/<int:step>/", wizard_views.funcionario_wizard_goto_step, name="funcionario_wizard_goto_step"),
    path("<int:pk>/wizard/", wizard_views.funcionario_wizard_edit, name="funcionario_wizard_edit"),
    path(
        "<int:pk>/wizard/goto/<int:step>/",
        wizard_views.funcionario_wizard_goto_step_edit,
        name="funcionario_wizard_goto_step_edit",
    ),
    path("<int:pk>/", views.FuncionarioDetailView.as_view(), name="funcionario_detail"),
    path("<int:pk>/desligar/", views.funcionario_desligar, name="funcionario_desligar"),
    path("<int:pk>/reativar/", views.funcionario_reativar, name="funcionario_reativar"),
    # Edição simples redirecionada para edição completa
    path("<int:pk>/editar/", views.FuncionarioCompleteView.as_view(), name="funcionario_update"),
    path("<int:pk>/excluir/", views.FuncionarioDeleteView.as_view(), name="funcionario_delete"),
    path("<int:pk>/completo/", views.FuncionarioCompleteView.as_view(), name="funcionario_complete"),
    # Regras de remuneração
    path(
        "<int:funcionario_pk>/remuneracao/regra/nova/",
        views.RemuneracaoRegraCreateView.as_view(),
        name="remuneracao_regra_create",
    ),
    path(
        "remuneracao/regra/<int:pk>/excluir/",
        views.RemuneracaoRegraDeleteView.as_view(),
        name="remuneracao_regra_delete",
    ),
    # URLs de férias
    path("ferias/", views.FeriasListView.as_view(), name="ferias_list"),
    path("<int:funcionario_pk>/ferias/", views.FeriasListView.as_view(), name="funcionario_ferias"),
    path("<int:funcionario_pk>/ferias/adicionar/", views.FeriasCreateView.as_view(), name="ferias_create"),
    path("ferias/<int:pk>/", views.FeriasDetailView.as_view(), name="ferias_detail"),
    path("ferias/<int:pk>/editar/", views.FeriasUpdateView.as_view(), name="ferias_update"),
    path("ferias/<int:pk>/excluir/", views.FeriasDeleteView.as_view(), name="ferias_delete"),
    # URLs de 13º salário
    path("decimo-terceiro/", views.DecimoTerceiroListView.as_view(), name="decimo_terceiro_list"),
    path(
        "<int:funcionario_pk>/decimo-terceiro/",
        views.DecimoTerceiroListView.as_view(),
        name="funcionario_decimo_terceiro",
    ),
    path(
        "<int:funcionario_pk>/decimo-terceiro/adicionar/",
        views.DecimoTerceiroCreateView.as_view(),
        name="decimo_terceiro_create",
    ),
    # URLs de folgas
    path("folgas/", views.FolgaListView.as_view(), name="folga_list"),
    path("<int:funcionario_pk>/folgas/", views.FolgaListView.as_view(), name="funcionario_folgas"),
    path("<int:funcionario_pk>/folgas/adicionar/", views.FolgaCreateView.as_view(), name="folga_create"),
    # URLs de cartão de ponto
    path("ponto/", views.CartaoPontoListView.as_view(), name="cartao_ponto_list"),
    path("<int:funcionario_pk>/ponto/", views.CartaoPontoListView.as_view(), name="funcionario_ponto"),
    path("<int:funcionario_pk>/ponto/registrar/", views.CartaoPontoCreateView.as_view(), name="cartao_ponto_create"),
    path("<int:funcionario_pk>/ponto/relatorio/", views.relatorio_ponto_funcionario, name="relatorio_ponto"),
    # URLs de benefícios
    path("beneficios/", views.BeneficioListView.as_view(), name="beneficio_list"),
    path("<int:funcionario_pk>/beneficios/", views.BeneficioListView.as_view(), name="funcionario_beneficios"),
    path("<int:funcionario_pk>/beneficios/adicionar/", views.BeneficioCreateView.as_view(), name="beneficio_create"),
    # URLs AJAX
    path("ajax/search/", views.funcionario_search_ajax, name="funcionario_search_ajax"),
    path("api/", include(router.urls)),
]

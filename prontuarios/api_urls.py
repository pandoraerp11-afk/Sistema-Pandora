from rest_framework.routers import DefaultRouter

from .api_views import AnamneseViewSet, AtendimentoViewSet, FotoEvolucaoViewSet

router = DefaultRouter()
## Rota de procedimentos removida (usar servicos)
router.register(r"atendimentos", AtendimentoViewSet)
router.register(r"fotos-evolucao", FotoEvolucaoViewSet)
router.register(r"anamneses", AnamneseViewSet)

urlpatterns = router.urls

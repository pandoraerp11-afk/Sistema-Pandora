from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET
from rest_framework.routers import DefaultRouter

from estoque.api import viewsets as v
from estoque.api.views.home import HomeEstoqueView, KPIsEstoqueView
from estoque.models import EstoqueSaldo, MovimentoEstoque


@login_required
@require_GET
def saldo_disponivel(request, produto_id, deposito_id):
    try:
        saldo = EstoqueSaldo.objects.get(produto_id=produto_id, deposito_id=deposito_id)
        return JsonResponse(
            {
                "total": float(saldo.quantidade),
                "reservado": float(saldo.reservado),
                "disponivel": float(saldo.disponivel),
            }
        )
    except EstoqueSaldo.DoesNotExist:
        return JsonResponse({"total": 0, "reservado": 0, "disponivel": 0}, status=404)


@login_required
@require_GET
def historico_reserva(request, reserva_id):
    movimentos = MovimentoEstoque.objects.filter(metadata__reserva_id=reserva_id).order_by("-criado_em")[:50]
    data = []
    for m in movimentos:
        data.append(
            {
                "data": m.criado_em.isoformat(),
                "tipo": m.tipo.lower(),
                "tipo_display": m.get_tipo_display(),
                "quantidade": float(m.quantidade),
                "usuario": m.usuario_executante.get_username() if m.usuario_executante else "-",
                "observacoes": m.motivo or "",
            }
        )
    return JsonResponse(data, safe=False)


app_name = "estoque_api"

router = DefaultRouter()
router.register(r"depositos", v.DepositoViewSet, basename="deposito")
router.register(r"saldos", v.EstoqueSaldoViewSet, basename="saldo")
router.register(r"movimentos", v.MovimentoEstoqueViewSet, basename="movimento")
router.register(r"reservas", v.ReservaEstoqueViewSet, basename="reserva")
router.register(r"pedidos-separacao", v.PedidoSeparacaoViewSet, basename="pedido-separacao")
router.register(r"pedidos-separacao-itens", v.PedidoSeparacaoItemViewSet, basename="pedido-separacao-item")
router.register(r"movimento-evidencias", v.MovimentoEvidenciaViewSet, basename="movimento-evidencia")
router.register(r"lotes", v.LoteViewSet, basename="lote")
router.register(r"numeros-serie", v.NumeroSerieViewSet, basename="numero-serie")
router.register(r"regras-reabastecimento", v.RegraReabastecimentoViewSet, basename="regra-reabastecimento")
router.register(r"inventarios-ciclicos", v.InventarioCiclicoViewSet, basename="inventario-ciclico")

urlpatterns = [
    path("", include(router.urls)),
    # Dashboard/Home e KPIs
    path("dashboard/home/", HomeEstoqueView.as_view(), name="dashboard-home"),
    path("dashboard/kpis/", KPIsEstoqueView.as_view(), name="dashboard-kpis"),
    path("saldo-disponivel/<int:produto_id>/<int:deposito_id>/", saldo_disponivel, name="saldo-disponivel"),
    path("historico-reserva/<int:reserva_id>/", historico_reserva, name="historico-reserva"),
]

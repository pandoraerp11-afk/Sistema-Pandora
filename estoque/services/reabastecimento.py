from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from estoque.models import EstoqueSaldo, RegraReabastecimento


def avaliar_regras_para_saldo(saldo: EstoqueSaldo):
    try:
        regra = RegraReabastecimento.objects.filter(produto=saldo.produto, deposito=saldo.deposito, ativo=True).first()
        if not regra:
            return None
        if regra.estrategia == "FORECAST":
            # Placeholder simples: tratar estoque_min dinamicamente (futuro: modelo estatístico)
            # Por enquanto reutiliza estoque_min configurado.
            pass
        if saldo.quantidade < regra.estoque_min:
            payload = {
                "event": "reabastecimento.alerta",
                "produto_id": saldo.produto_id,
                "deposito_id": saldo.deposito_id,
                "quantidade_atual": str(saldo.quantidade),
                "estoque_min": str(regra.estoque_min),
                "tenant_id": saldo.tenant_id,
            }
            _broadcast(payload)
            return payload
    except Exception:
        pass
    return None


def _broadcast(payload):
    try:
        layer = get_channel_layer()
        grupos = ["estoque_stream"]
        tenant_id = payload.get("tenant_id")
        if tenant_id:
            grupos.append(f"estoque_tenant_{tenant_id}")
        for g in grupos:
            async_to_sync(layer.group_send)(g, {"type": "estoque_event", "data": payload})
    except Exception:
        pass

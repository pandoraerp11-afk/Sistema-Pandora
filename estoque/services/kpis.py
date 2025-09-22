from datetime import timedelta

from django.core.cache import cache
from django.db.models import F, Max, Q, Sum
from django.utils import timezone

from estoque.models import EstoqueSaldo, MovimentoEstoque, PedidoSeparacao


def kpis_completas(periodo_dias: int = 30, slow_threshold_dias: int = 90, top_n: int = 10):
    """Calcula KPIs abrangentes de estoque.

    Parametros:
      periodo_dias: janela principal para giro / cobertura / shrinkage.
      slow_threshold_dias: dias sem saída para considerar item 'lento'.
      top_n: tamanho das listas de ranking.
    """
    now = timezone.now()
    cutoff = now - timedelta(days=periodo_dias)

    saldos_qs = EstoqueSaldo.objects.select_related("produto", "deposito")

    # Métricas de valor / quantidade
    agg_val = saldos_qs.aggregate(
        valor_total=Sum(F("quantidade") * F("custo_medio")),
        estoque_total_qtd=Sum("quantidade"),
        reservado_total=Sum("reservado"),
    )
    valor_total = agg_val["valor_total"] or 0
    estoque_total_qtd = agg_val["estoque_total_qtd"] or 0
    reservado_total = agg_val["reservado_total"] or 0
    disponivel_total = estoque_total_qtd - reservado_total
    itens_distintos = saldos_qs.count()
    valor_medio_item = (valor_total / itens_distintos) if itens_distintos else 0

    # Movimentos no período
    movimentos_periodo = MovimentoEstoque.objects.filter(criado_em__gte=cutoff)
    saidas_periodo = movimentos_periodo.filter(tipo="SAIDA").aggregate(q=Sum("quantidade"))["q"] or 0
    entradas_periodo = movimentos_periodo.filter(tipo="ENTRADA").aggregate(q=Sum("quantidade"))["q"] or 0
    perdas_periodo_qtd = (
        movimentos_periodo.filter(tipo__in=["PERDA", "DESCARTE", "VENCIMENTO"]).aggregate(q=Sum("quantidade"))["q"] or 0
    )
    perdas_periodo_valor = (
        movimentos_periodo.filter(tipo__in=["PERDA", "DESCARTE", "VENCIMENTO"]).aggregate(
            v=Sum(F("quantidade") * F("custo_unitario_snapshot"))
        )["v"]
        or 0
    )

    # Estoque médio aproximado (estoque_inicial ≈ estoque_final + entradas - saídas)
    estoque_final_aprox = estoque_total_qtd
    estoque_inicial_aprox = estoque_final_aprox + saidas_periodo - entradas_periodo
    estoque_medio = (
        (estoque_inicial_aprox + estoque_final_aprox) / 2
        if (estoque_inicial_aprox + estoque_final_aprox) != 0
        else estoque_final_aprox
    )

    # Giro e cobertura
    giro_periodo = (saidas_periodo / estoque_medio) if estoque_medio else 0
    giro_anualizado = giro_periodo * (365 / periodo_dias) if periodo_dias else giro_periodo
    media_saida_dia = (saidas_periodo / periodo_dias) if periodo_dias else 0
    cobertura_dias = (disponivel_total / media_saida_dia) if media_saida_dia else None

    # Shrinkage
    shrinkage_percent = (perdas_periodo_qtd / saidas_periodo) if saidas_periodo else 0
    shrinkage_valor_percent = (perdas_periodo_valor / valor_total) if valor_total else 0

    # Rupturas (disponivel <= 0)
    ruptura_count = saldos_qs.filter(Q(quantidade__lte=0) | Q(quantidade__lte=F("reservado"))).count()
    ruptura_percent = (ruptura_count / itens_distintos) if itens_distintos else 0

    # Itens lentos / rápidos (com base em últimas saídas)
    ultima_saida_por_prod = (
        MovimentoEstoque.objects.filter(tipo="SAIDA").values("produto_id").annotate(ultima=Max("criado_em"))
    )
    # Mapear produto -> dias desde última saída
    dias_sem_saida = {}
    for row in ultima_saida_por_prod:
        dias_sem_saida[row["produto_id"]] = (now - row["ultima"]).days
    # Lentos (sem saída > slow_threshold_dias) ou sem nenhuma saída
    ids_saldos = list(saldos_qs.values_list("produto_id", flat=True))
    slow_items = []
    fast_items = []
    for pid in ids_saldos:
        dias = dias_sem_saida.get(pid, 9999)
        if dias >= slow_threshold_dias:
            slow_items.append((pid, dias))
        else:
            fast_items.append((pid, dias))
    slow_items.sort(key=lambda x: x[1], reverse=True)
    fast_items.sort(key=lambda x: x[1])
    slow_items = slow_items[:top_n]
    fast_items = fast_items[:top_n]

    # Pedidos picking SLA (reaproveita lógica existente de sla_picking(7) porém para janela principal também)
    pedidos_periodo = PedidoSeparacao.objects.filter(
        criado_em__gte=cutoff, pronto_em__isnull=False, inicio_preparo__isnull=False
    )
    if pedidos_periodo.exists():
        duracoes = [(p.pronto_em - p.inicio_preparo).total_seconds() / 60 for p in pedidos_periodo]
        sla_media_min = sum(duracoes) / len(duracoes)
    else:
        sla_media_min = 0

    # Movimentos pendentes de aprovação (perdas) e valor estimado
    pendentes = MovimentoEstoque.objects.filter(
        aprovacao_status="PENDENTE", tipo__in=["PERDA", "DESCARTE", "VENCIMENTO"]
    )
    pendentes_qtd = pendentes.aggregate(q=Sum("quantidade"))["q"] or 0
    pendentes_valor = pendentes.aggregate(v=Sum(F("quantidade") * F("custo_unitario_snapshot")))["v"] or 0

    return {
        "periodo_dias": periodo_dias,
        "valor_total": valor_total,
        "estoque_total_qtd": estoque_total_qtd,
        "reservado_total_qtd": reservado_total,
        "disponivel_total_qtd": disponivel_total,
        "itens_distintos": itens_distintos,
        "valor_medio_item": valor_medio_item,
        "saidas_periodo_qtd": saidas_periodo,
        "entradas_periodo_qtd": entradas_periodo,
        "perdas_periodo_qtd": perdas_periodo_qtd,
        "perdas_periodo_valor": perdas_periodo_valor,
        "estoque_medio_aprox_qtd": estoque_medio,
        "giro_periodo": giro_periodo,
        "giro_anualizado": giro_anualizado,
        "cobertura_dias": cobertura_dias,
        "shrinkage_percent_qtd": shrinkage_percent,
        "shrinkage_percent_valor": shrinkage_valor_percent,
        "ruptura_count": ruptura_count,
        "ruptura_percent": ruptura_percent,
        "itens_lentos_top": [{"produto_id": pid, "dias_sem_saida": dias} for pid, dias in slow_items],
        "itens_rapidos_top": [{"produto_id": pid, "dias_sem_saida": dias} for pid, dias in fast_items],
        "sla_picking_media_minutos_periodo": sla_media_min,
        "perdas_pendentes_qtd": pendentes_qtd,
        "perdas_pendentes_valor": pendentes_valor,
    }


def giro_estoque(dias=30):
    cutoff = timezone.now() - timedelta(days=dias)
    saldos = EstoqueSaldo.objects.aggregate(estoque_total=Sum("quantidade"))
    estoque_total = saldos["estoque_total"] or 0
    saidas_periodo = (
        MovimentoEstoque.objects.filter(tipo="SAIDA", criado_em__gte=cutoff).aggregate(q=Sum("quantidade"))["q"] or 0
    )
    giro = (saidas_periodo / estoque_total) if estoque_total else 0
    return {"periodo_dias": dias, "giro": giro, "saidas_periodo": saidas_periodo, "estoque_total": estoque_total}


def aging_classes():
    # Simplificação: usa última entrada para cada produto
    now = timezone.now()
    faixas = {"0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    entradas = MovimentoEstoque.objects.filter(tipo="ENTRADA").values("produto_id").annotate(last=Max("criado_em"))
    for e in entradas:
        diff = (now - e["last"]).days
        if diff <= 30:
            faixas["0_30"] += 1
        elif diff <= 60:
            faixas["31_60"] += 1
        elif diff <= 90:
            faixas["61_90"] += 1
        else:
            faixas["90_plus"] += 1
    total = sum(faixas.values()) or 1
    return {k: v / total for k, v in faixas.items()}


def shrinkage_percent(dias=30):
    cutoff = timezone.now() - timedelta(days=dias)
    perdas = (
        MovimentoEstoque.objects.filter(tipo__in=["PERDA", "DESCARTE", "VENCIMENTO"], criado_em__gte=cutoff).aggregate(
            q=Sum("quantidade")
        )["q"]
        or 0
    )
    saidas = (
        MovimentoEstoque.objects.filter(tipo="SAIDA", criado_em__gte=cutoff).aggregate(q=Sum("quantidade"))["q"] or 0
    )
    pct = (perdas / saidas) if saidas else 0
    return {"periodo_dias": dias, "perdas": perdas, "saidas": saidas, "shrinkage_percent": pct}


def sla_picking(dias=7):
    cutoff = timezone.now() - timedelta(days=dias)
    pedidos = PedidoSeparacao.objects.filter(
        criado_em__gte=cutoff, pronto_em__isnull=False, inicio_preparo__isnull=False
    )
    if not pedidos.exists():
        return {"periodo_dias": dias, "sla_media_minutos": 0}
    duracoes = [(p.pronto_em - p.inicio_preparo).total_seconds() / 60 for p in pedidos]
    media = sum(duracoes) / len(duracoes)
    return {"periodo_dias": dias, "sla_media_minutos": media}


def coletar_kpis(tenant=None, ttl=60):
    chave = f"estoque_kpis:{tenant.id if tenant else 'global'}"
    data = cache.get(chave)
    if data:
        return data
    completas = kpis_completas(30)
    data = {
        "completas_30d": completas,
        "giro_30d": completas["giro_periodo"],
        "shrinkage_30d_percent": completas["shrinkage_percent_qtd"],
        "sla_picking_30d_minutos": completas["sla_picking_media_minutos_periodo"],
        "aging": aging_classes(),
    }
    cache.set(chave, data, ttl)
    return data


def invalidar_kpis(tenant=None):
    cache.delete(f"estoque_kpis:{tenant.id if tenant else 'global'}")

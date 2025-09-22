import contextlib
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from estoque.models import (
    Deposito,
    EstoqueSaldo,
    Lote,
    MovimentoEstoque,
    MovimentoLote,
    MovimentoNumeroSerie,
    NumeroSerie,
)
from estoque.services.kpis import invalidar_kpis
from estoque.signals import movimento_registrado
from shared.exceptions import NegocioError, SaldoInsuficienteError

# Serviço simplificado Fase 1 - expandido depois com valuation/FIFO.


def _obter_saldo_lock(produto, deposito):
    saldo, _ = EstoqueSaldo.objects.select_for_update().get_or_create(produto=produto, deposito=deposito)
    return saldo


@transaction.atomic
def registrar_entrada(
    produto, deposito: Deposito, quantidade: Decimal, custo_unitario: Decimal, usuario, tenant=None, **kwargs
):
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    # Permissão necessária
    if usuario and not getattr(usuario, "is_superuser", False):
        # Permissão obrigatória apenas se flag global exigir ou se usuário possuir alguma perm de estoque (indicando regime estrito)
        try:
            exige_perm = getattr(settings, "ESTOQUE_EXIGE_PERMISSAO_OPERAR", False)
        except Exception:
            exige_perm = False
        if (
            exige_perm or usuario.user_permissions.filter(codename__startswith="pode_estoque").exists()
        ) and not usuario.has_perm("estoque.pode_operar_movimento"):
            raise NegocioError("Usuário não possui permissão para operar movimento.")
    saldo = _obter_saldo_lock(produto, deposito)

    snapshot_antes = {
        "saldo_quantidade": str(saldo.quantidade),
        "saldo_reservado": str(saldo.reservado),
    }
    # Valuation: FIFO cria camadas, média pondera
    from estoque.services.valuation import is_fifo, registrar_entrada_fifo_e_atualizar

    if is_fifo(produto):
        registrar_entrada_fifo_e_atualizar(produto, deposito, quantidade, custo_unitario, tenant=tenant)
        # saldo.custo_medio já atualizado por valuation
    else:
        # custo médio ponderado
        if saldo.quantidade > 0:
            novo_custo = ((saldo.quantidade * saldo.custo_medio) + (quantidade * custo_unitario)) / (
                saldo.quantidade + quantidade
            )
        else:
            novo_custo = custo_unitario
        saldo.custo_medio = novo_custo

    saldo.quantidade = saldo.quantidade + quantidade
    saldo.save(update_fields=["quantidade", "custo_medio", "atualizado_em"])
    mov = MovimentoEstoque.objects.create(
        produto=produto,
        deposito_destino=deposito,
        tipo="ENTRADA",
        quantidade=quantidade,
        custo_unitario_snapshot=custo_unitario,
        usuario_executante=usuario,
        tenant=tenant,
        metadata={**kwargs.get("metadata", {}), "snapshot_antes": snapshot_antes}
        if kwargs.get("metadata")
        else {"snapshot_antes": snapshot_antes},
        **{
            k: v
            for k, v in kwargs.items()
            if k in ["ref_externa", "motivo", "solicitante_tipo", "solicitante_id", "solicitante_nome_cache"]
        },
    )
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=mov, acao="ENTRADA")
    invalidar_kpis(tenant)
    # Processar lotes (se produto controla lote)
    lotes_info = kwargs.get("lotes")  # lista de dicts {'codigo':..., 'quantidade':..., 'validade':date}
    if produto.controla_lote and lotes_info:
        restante = quantidade
        for li in lotes_info:
            if restante <= 0:
                break
            codigo = li["codigo"]
            qtd_lote = Decimal(str(li.get("quantidade", restante)))
            if qtd_lote <= 0:
                continue
            validade = li.get("validade")
            lote, created = Lote.objects.get_or_create(
                produto=produto, codigo=codigo, defaults={"tenant": tenant, "deposito": deposito, "validade": validade}
            )
            if not created:
                # Atualiza deposito/validade se fornecido
                changed = False
                if lote.deposito_id != deposito.id:
                    lote.deposito = deposito
                    changed = True
                if validade and lote.validade != validade:
                    lote.validade = validade
                    changed = True
                if changed:
                    lote.save(update_fields=["deposito", "validade"])
            lote.quantidade_atual = lote.quantidade_atual + qtd_lote
            lote.save(update_fields=["quantidade_atual"])
            MovimentoLote.objects.create(movimento=mov, lote=lote, quantidade=qtd_lote)
            restante -= qtd_lote
        if restante > 0:
            # distribuir saldo remanescente no primeiro lote informado
            li0 = lotes_info[0]
            lote0, _ = Lote.objects.get_or_create(
                produto=produto,
                codigo=li0["codigo"],
                defaults={"tenant": tenant, "deposito": deposito, "validade": li0.get("validade")},
            )
            lote0.quantidade_atual += restante
            lote0.save(update_fields=["quantidade_atual"])
            MovimentoLote.objects.create(movimento=mov, lote=lote0, quantidade=restante)
    # Processar números de série
    numeros_serie_codigos = kwargs.get("numeros_serie")  # lista de strings
    if produto.controla_numero_serie and numeros_serie_codigos:
        if len(numeros_serie_codigos) != int(quantidade):
            raise NegocioError("Quantidade de números de série deve corresponder à quantidade.")
        for codigo in numeros_serie_codigos:
            ns, created = NumeroSerie.objects.get_or_create(
                codigo=codigo, defaults={"produto": produto, "tenant": tenant, "deposito_atual": deposito}
            )
            if not created:
                if ns.status != "ATIVO":
                    raise NegocioError(f"Número de série {codigo} não está disponível para entrada.")
                ns.deposito_atual = deposito
                ns.status = "ATIVO"
                ns.save(update_fields=["deposito_atual", "status"])
            MovimentoNumeroSerie.objects.create(movimento=mov, numero_serie=ns)
    return mov


@transaction.atomic
def registrar_saida(
    produto, deposito: Deposito, quantidade: Decimal, usuario, custo_unitario=None, tenant=None, **kwargs
):
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    if usuario and not getattr(usuario, "is_superuser", False):
        try:
            exige_perm = getattr(settings, "ESTOQUE_EXIGE_PERMISSAO_OPERAR", False)
        except Exception:
            exige_perm = False
        if (
            exige_perm or usuario.user_permissions.filter(codename__startswith="pode_estoque").exists()
        ) and not usuario.has_perm("estoque.pode_operar_movimento"):
            raise NegocioError("Usuário não possui permissão para operar movimento.")
    saldo = _obter_saldo_lock(produto, deposito)
    if saldo.quantidade - saldo.reservado < quantidade:
        raise SaldoInsuficienteError(produto.id, deposito.id, quantidade, saldo.quantidade - saldo.reservado)

    snapshot_antes = {
        "saldo_quantidade": str(saldo.quantidade),
        "saldo_reservado": str(saldo.reservado),
    }
    # Valuation FIFO se produto configurado
    custo_saida = custo_unitario
    if not custo_saida:
        from estoque.services.valuation import consumir_fifo_e_atualizar, is_fifo

        if is_fifo(produto):
            try:
                custo_saida = consumir_fifo_e_atualizar(produto, deposito, quantidade)
            except Exception:
                custo_saida = saldo.custo_medio
        else:
            custo_saida = saldo.custo_medio

    saldo.quantidade = saldo.quantidade - quantidade
    saldo.save(update_fields=["quantidade", "atualizado_em"])
    mov = MovimentoEstoque.objects.create(
        produto=produto,
        deposito_origem=deposito,
        tipo="SAIDA",
        quantidade=quantidade,
        custo_unitario_snapshot=custo_saida,
        usuario_executante=usuario,
        tenant=tenant,
        metadata={**kwargs.get("metadata", {}), "snapshot_antes": snapshot_antes}
        if kwargs.get("metadata")
        else {"snapshot_antes": snapshot_antes},
        **{
            k: v
            for k, v in kwargs.items()
            if k in ["ref_externa", "motivo", "solicitante_tipo", "solicitante_id", "solicitante_nome_cache"]
        },
    )
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=mov, acao="SAIDA")
    invalidar_kpis(tenant)
    # Lotes: decrementar
    lotes_info = kwargs.get("lotes")  # lista [{'id':..,'quantidade':..}] ou [{'codigo':..,'quantidade':..}]
    if produto.controla_lote:
        if not lotes_info:
            raise NegocioError("É necessário informar lotes para saída deste produto.")
        total_lotes = Decimal("0")
        for li in lotes_info:
            qtd_lote = Decimal(str(li.get("quantidade", "0")))
            if qtd_lote <= 0:
                raise NegocioError("Quantidade inválida em lote.")
            if "id" in li:
                lote = Lote.objects.select_for_update().get(id=li["id"], produto=produto)
            else:
                lote = Lote.objects.select_for_update().get(produto=produto, codigo=li["codigo"])
            # Bloquear uso de lote vencido em saída normal
            if lote.validade and lote.validade < timezone.now().date():
                raise NegocioError(f"Lote {lote.codigo} vencido não pode ser utilizado em saída normal.")
            if lote.deposito_id and lote.deposito_id != deposito.id:
                raise NegocioError(f"Lote {lote.codigo} não está no depósito informado.")
            if lote.quantidade_atual - lote.quantidade_reservada < qtd_lote:
                raise NegocioError(f"Lote {lote.codigo} saldo insuficiente.")
            lote.quantidade_atual -= qtd_lote
            lote.save(update_fields=["quantidade_atual"])
            MovimentoLote.objects.create(movimento=mov, lote=lote, quantidade=qtd_lote)
            total_lotes += qtd_lote
        if total_lotes != quantidade:
            raise NegocioError("Soma das quantidades dos lotes difere da quantidade do movimento.")
    # Números de série: validar e marcar movimentado
    numeros_serie_codigos = kwargs.get("numeros_serie")
    if produto.controla_numero_serie:
        if not numeros_serie_codigos:
            raise NegocioError("É necessário informar números de série para saída deste produto.")
        if len(numeros_serie_codigos) != int(quantidade):
            raise NegocioError("Quantidade de números de série deve corresponder à quantidade.")
        for codigo in numeros_serie_codigos:
            ns = NumeroSerie.objects.select_for_update().get(codigo=codigo, produto=produto)
            if ns.status not in ["ATIVO", "MOVIMENTADO"]:
                raise NegocioError(f"Número de série {codigo} não disponível para saída.")
            if ns.deposito_atual_id != deposito.id:
                raise NegocioError(f"Número de série {codigo} não está no depósito informado.")
            ns.status = "MOVIMENTADO"
            ns.save(update_fields=["status"])
            MovimentoNumeroSerie.objects.create(movimento=mov, numero_serie=ns)
    try:
        from estoque.services.reabastecimento import avaliar_regras_para_saldo

        avaliar_regras_para_saldo(saldo)
    except Exception:
        pass
    return mov


@transaction.atomic
def transferir(
    produto, deposito_origem: Deposito, deposito_destino: Deposito, quantidade: Decimal, usuario, tenant=None, **kwargs
):
    if deposito_origem == deposito_destino:
        raise NegocioError("Depósitos origem e destino devem ser diferentes.")
    if quantidade <= 0:
        raise NegocioError("Quantidade deve ser positiva.")
    saldo_origem = _obter_saldo_lock(produto, deposito_origem)
    if saldo_origem.quantidade - saldo_origem.reservado < quantidade:
        raise SaldoInsuficienteError(
            produto.id, deposito_origem.id, quantidade, saldo_origem.quantidade - saldo_origem.reservado
        )
    saldo_destino = _obter_saldo_lock(produto, deposito_destino)

    snapshot_antes = {
        "saldo_origem_qtd": str(saldo_origem.quantidade),
        "saldo_destino_qtd": str(saldo_destino.quantidade),
    }
    # Retirar origem
    saldo_origem.quantidade = saldo_origem.quantidade - quantidade
    saldo_origem.save(update_fields=["quantidade", "atualizado_em"])
    # Entrada destino sem recalcular custo médio (herda custo médio origem neste estágio)
    saldo_destino.quantidade = saldo_destino.quantidade + quantidade
    if saldo_destino.custo_medio == 0:
        saldo_destino.custo_medio = saldo_origem.custo_medio
    saldo_destino.save(update_fields=["quantidade", "custo_medio", "atualizado_em"])
    # Criar movimento único de transferência
    mov = MovimentoEstoque.objects.create(
        produto=produto,
        deposito_origem=deposito_origem,
        deposito_destino=deposito_destino,
        tipo="TRANSFER",
        quantidade=quantidade,
        custo_unitario_snapshot=saldo_origem.custo_medio,
        usuario_executante=usuario,
        tenant=tenant,
        metadata={**kwargs.get("metadata", {}), "snapshot_antes": snapshot_antes}
        if kwargs.get("metadata")
        else {"snapshot_antes": snapshot_antes},
        **{
            k: v
            for k, v in kwargs.items()
            if k in ["ref_externa", "motivo", "solicitante_tipo", "solicitante_id", "solicitante_nome_cache"]
        },
    )
    with contextlib.suppress(Exception):
        movimento_registrado.send(sender=MovimentoEstoque, movimento=mov, acao="TRANSFER")
    invalidar_kpis(tenant)
    try:
        from estoque.services.reabastecimento import avaliar_regras_para_saldo

        avaliar_regras_para_saldo(saldo_origem)
    except Exception:
        pass
    return mov

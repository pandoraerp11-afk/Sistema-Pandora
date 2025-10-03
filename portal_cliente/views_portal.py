"""Views do Portal Cliente (Fases 1 e 2).

Foco desta revisão:
 - Remover broad except gerais substituindo por exceções específicas.
 - Garantir mensagens de erro sempre string (evitar None).
 - Parsing de datas timezone-aware sem uso direto de datetime.strptime (evita DTZ007).
 - Preparar terreno para futura redução de complexidade sem alterar lógica.
 - Adicionar imports de typing.
"""

from datetime import date, datetime, time, timedelta

# ruff: noqa: I001 - ordenação de imports mantida agrupando stdlib/django/domínio
from typing import cast

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import http_date

from agendamentos.models import Agendamento
from funcionarios.models import Funcionario
from prontuarios.models import Atendimento, FotoEvolucao
from prontuarios.services import AtendimentoAgendamentoService
from servicos.models import Servico
from shared.portal.decorators import cliente_portal_required

from .conf import (
    get_cache_ttl,
    get_checkin_antecedencia_minutos,
    get_finalizacao_tolerancia_horas,
    get_checkin_tolerancia_pos_minutos,
)
from .metrics import (
    PORTAL_CLIENTE_PAGE_HITS,
    inc_action,
    inc_throttle,
    track_action,
    inc_action_error_kind,
)
from .repositories import FotoEvolucaoRepository
from .services import PortalClienteService
from .session_helpers import ensure_tenant_session
from .throttle import check_throttle_auto, get_retry_after_seconds


def _throttle_response(user_id: int, endpoint: str, scope: int | str | None = None) -> JsonResponse:
    """Gera resposta 429 padronizada com Retry-After dinâmico."""
    inc_throttle(endpoint)
    retry_after = get_retry_after_seconds(user_id, endpoint, scope=scope)
    resp = JsonResponse(
        {"success": False, "error": "Limite de requisições atingido. Tente novamente em instantes."},
        status=429,
    )
    resp["Retry-After"] = str(retry_after)
    return resp


def _classify_error_kind(action: str, raw_msg: str | Exception) -> str:
    """Mapeia mensagens para tipos de erro normalizados (complexidade reduzida).

    Estratégia: converte para lower e verifica listas de tuplas (predicate -> kind)
    específicas por ação. Primeiro match vence. Fallback: generic.
    """
    msg = str(raw_msg).lower()
    rules: dict[str, list[tuple[str | tuple[str, ...], str]]] = {
        "checkin": [
            ("cedo", "checkin_cedo"),
            (("expirad", "fora da janela"), "checkin_expirado"),
            ("status", "checkin_status_invalido"),
        ],
        "finalizar": [
            (("expirada", "janela"), "finalizacao_expirada"),
            ("nao encontrado", "atendimento_inexistente"),
        ],
        "avaliar": [
            (("nota", "invalida"), "nota_invalida"),
            (("ja registrada", "já registrada", "ja aval"), "avaliacao_duplicada"),
            ("nao encontrado", "atendimento_inexistente"),
        ],
    }
    for predicate, kind in rules.get(action, []):
        if isinstance(predicate, tuple):
            # Match se TODAS as partes (ou alguma?) -> aqui definimos que qualquer substring basta
            if any(p in msg for p in predicate):
                return kind
        elif predicate in msg:
            return kind
    return "generic"


@cliente_portal_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard principal do cliente - Fase 1."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="dashboard").inc()
    with track_action("render_dashboard"):
        # Obter conta ativa do cliente
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)

        # Usar service para construir dashboard com dados reais
        dashboard_data = PortalClienteService.build_dashboard(conta_cliente)

        context = {
            "conta_cliente": conta_cliente,
            "proximos_agendamentos": dashboard_data["proximos_agendamentos"],
            "historico_recente": dashboard_data["historico_recente"],
            "fotos_recentes": dashboard_data["fotos_recentes"],
            "estatisticas": dashboard_data["estatisticas"],
        }
        return render(request, "portal_cliente/dashboard.html", context)


@cliente_portal_required
def documentos_list(request: HttpRequest) -> HttpResponse:
    """Lista de documentos disponíveis."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="documentos_list").inc()
    with track_action("render_documentos_list"):
        contas = request.contas_cliente
        return render(request, "portal_cliente/documentos_list.html", {"contas": contas})


# ===== AGENDAMENTOS - FASE 1 =====


@cliente_portal_required
def agendamentos_lista(request: HttpRequest) -> HttpResponse:
    """Lista agendamentos do cliente."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="agendamentos_lista").inc()

    conta_cliente = PortalClienteService.get_conta_ativa(request.user)
    cliente = conta_cliente.cliente

    # Filtros
    status_filter = request.GET.get("status", "todos")
    data_filter = request.GET.get("data", "futuros")

    # Query base
    agendamentos = (
        Agendamento.objects.filter(tenant=cliente.tenant, cliente=cliente)
        .select_related("servico", "profissional")
        .order_by("-data_inicio")
    )

    # Aplicar filtros
    hoje = timezone.now()
    if data_filter == "futuros":
        agendamentos = agendamentos.filter(data_inicio__gte=hoje)
    elif data_filter == "passados":
        agendamentos = agendamentos.filter(data_inicio__lt=hoje)

    if status_filter != "todos":
        agendamentos = agendamentos.filter(status=status_filter.upper())

    # Paginação
    paginator = Paginator(agendamentos, 10)
    page = request.GET.get("page")
    agendamentos_page = paginator.get_page(page)

    context = {
        "conta_cliente": conta_cliente,
        "agendamentos": agendamentos_page,
        "status_filter": status_filter,
        "data_filter": data_filter,
    }
    return render(request, "portal_cliente/agendamentos_lista.html", context)


@cliente_portal_required
def novo_agendamento(request: HttpRequest) -> HttpResponse:
    """Interface para criar novo agendamento."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="novo_agendamento").inc()

    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    if request.method == "POST":
        slot_id = request.POST.get("slot_id")
        servico_id = request.POST.get("servico_id")  # nome definitivo
        observacoes = request.POST.get("observacoes", "").strip()

        # Validação simples fora do try (evita TRY301)
        if not slot_id or not servico_id:
            messages.error(request, "Slot e serviço são obrigatórios")
        else:
            try:
                agendamento = PortalClienteService.criar_agendamento_cliente(
                    conta_cliente=conta_cliente,
                    slot_id=int(slot_id),
                    servico_id=int(servico_id),
                    observacoes=observacoes if observacoes else None,
                )
                messages.success(
                    request,
                    f"Agendamento criado com sucesso! Data: {agendamento.data_inicio.strftime('%d/%m/%Y às %H:%M')}",
                )
                return redirect("portal_cliente:agendamentos_lista")
            except (ValueError, PermissionDenied) as e:  # erros esperados
                messages.error(request, f"Erro ao criar agendamento: {e}")

        # Buscar serviços clínicos disponíveis
        servicos = Servico.objects.filter(tenant=conta_cliente.cliente.tenant, ativo=True, is_clinical=True).order_by(
            "nome_servico",
        )

    # Buscar profissionais disponíveis
    profissionais = Funcionario.objects.filter(
        tenant=conta_cliente.cliente.tenant,
        ativo=True,
        tipo_funcionario="PROFISSIONAL",
    ).order_by("nome")

    context = {
        "conta_cliente": conta_cliente,
        "servicos": servicos,
        "profissionais": profissionais,
    }
    return render(request, "portal_cliente/novo_agendamento.html", context)


@cliente_portal_required
def cancelar_agendamento(request: HttpRequest, agendamento_id: int) -> HttpResponse:
    """Cancelar agendamento existente."""
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    if request.method == "POST":
        try:
            motivo = request.POST.get("motivo", "").strip()

            agendamento = PortalClienteService.cancelar_agendamento_cliente(
                conta_cliente=conta_cliente,
                agendamento_id=agendamento_id,
                motivo=motivo if motivo else None,
            )

            messages.success(request, "Agendamento cancelado com sucesso!")
            return redirect("portal_cliente:agendamentos_lista")

        except (ValueError, PermissionDenied) as e:
            messages.error(request, f"Erro ao cancelar agendamento: {e}")
            return redirect("portal_cliente:agendamentos_lista")

    # Verificar se pode cancelar
    pode_cancelar, erro = PortalClienteService.pode_cancelar_agendamento(conta_cliente, agendamento_id)

    if not pode_cancelar:
        messages.error(request, erro or "Não é possível cancelar este agendamento.")
        return redirect("portal_cliente:agendamentos_lista")

    # Buscar agendamento para confirmação
    agendamento = get_object_or_404(
        Agendamento,
        id=agendamento_id,
        cliente=conta_cliente.cliente,
        tenant=conta_cliente.cliente.tenant,
    )

    context = {
        "conta_cliente": conta_cliente,
        "agendamento": agendamento,
    }
    return render(request, "portal_cliente/cancelar_agendamento.html", context)


# ===== HISTÓRICO DE ATENDIMENTOS - FASE 1 =====


@cliente_portal_required
def historico_atendimentos(request: HttpRequest) -> HttpResponse:
    """Histórico seguro de atendimentos (sem dados sensíveis)."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="historico_atendimentos").inc()

    conta_cliente = PortalClienteService.get_conta_ativa(request.user)
    cliente = conta_cliente.cliente

    # Apenas atendimentos concluídos
    atendimentos = (
        Atendimento.objects.filter(tenant=cliente.tenant, cliente=cliente, status="CONCLUIDO")
        .select_related("servico", "profissional")
        .order_by("-data_atendimento")
    )

    # Paginação
    paginator = Paginator(atendimentos, 15)
    page = request.GET.get("page")
    atendimentos_page = paginator.get_page(page)

    context = {
        "conta_cliente": conta_cliente,
        "atendimentos": atendimentos_page,
    }
    return render(request, "portal_cliente/historico_atendimentos.html", context)


@cliente_portal_required
def detalhe_atendimento(request: HttpRequest, atendimento_id: int) -> HttpResponse:
    """Detalhe seguro de um atendimento específico."""
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    atendimento = get_object_or_404(
        Atendimento,
        id=atendimento_id,
        cliente=conta_cliente.cliente,
        tenant=conta_cliente.cliente.tenant,
        status="CONCLUIDO",
    )

    # Buscar fotos do atendimento (apenas thumbnails visíveis ao cliente)
    fotos = FotoEvolucaoRepository.do_atendimento(atendimento)

    context = {
        "conta_cliente": conta_cliente,
        "atendimento": atendimento,
        "fotos": fotos,
    }
    return render(request, "portal_cliente/detalhe_atendimento.html", context)


# ===== GALERIA DE FOTOS - FASE 1 =====


@cliente_portal_required
def galeria_fotos(request: HttpRequest) -> HttpResponse:
    """Galeria de fotos com thumbnails (nunca originais)."""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="galeria_fotos").inc()

    conta_cliente = PortalClienteService.get_conta_ativa(request.user)
    cliente = conta_cliente.cliente

    # Thumbnails de fotos visíveis ao cliente (independente de atendimento existir)
    fotos = FotoEvolucaoRepository.paginadas(cliente.tenant, cliente)

    # Paginação
    paginator = Paginator(fotos, 20)
    page = request.GET.get("page")
    fotos_page = paginator.get_page(page)

    context = {
        "conta_cliente": conta_cliente,
        "fotos": fotos_page,
    }
    return render(request, "portal_cliente/galeria_fotos.html", context)


@cliente_portal_required
def visualizar_foto(request: HttpRequest, foto_id: int) -> HttpResponse:
    """Visualização de foto individual (apenas thumbnail/webp)."""
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    foto = get_object_or_404(
        FotoEvolucao,
        id=foto_id,
        cliente=conta_cliente.cliente,
        tenant=conta_cliente.cliente.tenant,
        visivel_cliente=True,
    )

    # Verificar se tem thumbnail (ou imagem principal)
    if not foto.imagem_thumbnail and not foto.imagem:
        msg_nao_disp = "Imagem não disponível"
        raise Http404(msg_nao_disp)

    context = {
        "conta_cliente": conta_cliente,
        "foto": foto,
    }
    return render(request, "portal_cliente/visualizar_foto.html", context)


# ===== ENDPOINTS AJAX - FASE 1 =====


@cliente_portal_required
def slots_disponiveis_ajax(request: HttpRequest) -> JsonResponse:
    """AJAX: Buscar slots disponíveis para agendamento (throttle central)."""
    ensure_tenant_session(request)
    if check_throttle_auto(cast("int", request.user.id), "slots"):
        return _throttle_response(cast("int", request.user.id), "slots")
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    # Parâmetros de filtro
    # login_required garante user autenticado; cast para satisfazer type checker
    data_inicio_raw = request.GET.get("data_inicio")
    data_fim_raw = request.GET.get("data_fim")
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    servico_id = request.GET.get("servico_id")
    profissional_id = request.GET.get("profissional_id")

    try:
        # Converter datas se fornecidas (timezone-aware sem datetime.strptime para evitar DTZ007)
        if data_inicio_raw:
            d_inicio = date.fromisoformat(data_inicio_raw)
            data_inicio = timezone.make_aware(datetime.combine(d_inicio, time.min), timezone.get_current_timezone())
        if data_fim_raw:
            d_fim = date.fromisoformat(data_fim_raw)
            data_fim = timezone.make_aware(
                datetime.combine(d_fim, time.max),
                timezone.get_current_timezone(),
            )

        slots = PortalClienteService.listar_slots_disponiveis(
            conta_cliente=conta_cliente,
            data_inicio=data_inicio,
            data_fim=data_fim,
            servico_id=int(servico_id) if servico_id else None,
            profissional_id=int(profissional_id) if profissional_id else None,
        )

        slots_data = [
            {
                "id": s.id,
                "horario": s.horario.isoformat(),
                "horario_display": s.horario.strftime("%d/%m/%Y às %H:%M"),
                "profissional": s.profissional.nome,
                "profissional_id": s.profissional.id,
                "capacidade_disponivel": s.capacidade_total - s.capacidade_utilizada,
            }
            for s in slots
        ]
        return JsonResponse({"success": True, "slots": slots_data})
    except (ValueError, PermissionDenied) as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def servicos_ajax(request: HttpRequest) -> JsonResponse | HttpResponse:
    """AJAX: Lista serviços clínicos disponíveis (throttle + TTL configurável)."""
    ensure_tenant_session(request)
    if check_throttle_auto(cast("int", request.user.id), "servicos"):
        return _throttle_response(cast("int", request.user.id), "servicos")
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        tenant = conta_cliente.cliente.tenant

        ttl = get_cache_ttl()
        data_cache_key = f"portal_serv_data_{tenant.id}"
        meta_cache_key = f"portal_serv_meta_{tenant.id}"

        cached = cache.get(data_cache_key)
        meta = cache.get(meta_cache_key)

        if not cached or not meta:
            # Carrega e serializa
            servicos_qs = (
                Servico.objects.filter(tenant=tenant, ativo=True, is_clinical=True)
                .select_related("perfil_clinico")
                .order_by("nome_servico")
            )
            servicos_data = [
                {
                    "id": proc.id,
                    "nome": proc.nome_servico,
                    "descricao": proc.descricao_curta or proc.descricao,
                    "duracao_estimada": (
                        str(getattr(getattr(proc, "perfil_clinico", None), "duracao_estimada", ""))
                        if getattr(proc, "perfil_clinico", None)
                        else None
                    ),
                    "valor_base": float(proc.preco_base) if proc.preco_base is not None else None,
                }
                for proc in servicos_qs
            ]
            # Metadados para ETag
            agg = Servico.objects.filter(tenant=tenant, ativo=True, is_clinical=True).aggregate(
                m=Max("ultima_atualizacao"),
                c=Count("id"),
            )
            last_updated = agg["m"] or timezone.now()
            count = agg["c"] or 0
            etag = f'W/"servico-{tenant.id}-{int(last_updated.timestamp())}-{count}"'
            meta = {"etag": etag, "last_updated": last_updated, "count": count}
            cache.set(data_cache_key, servicos_data, ttl)
            cache.set(meta_cache_key, meta, ttl)
            cached = servicos_data

        # Resposta condicional - preparar objeto e retornar apenas no bloco else do try (TRY300)
        client_etag = request.META.get("HTTP_IF_NONE_MATCH")
        if client_etag and meta["etag"] == client_etag:
            response = HttpResponse(status=304)
            response["ETag"] = meta["etag"]
            response["Cache-Control"] = f"private, max-age={ttl}"
            response["Last-Modified"] = http_date(meta["last_updated"].timestamp())
        else:
            response = JsonResponse({"success": True, "servicos": cached})
            response["ETag"] = meta["etag"]
            response["Cache-Control"] = f"private, max-age={ttl}"
            response["Last-Modified"] = http_date(meta["last_updated"].timestamp())
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    else:  # TRY300: código executado apenas se não houve exceção
        return response


@cliente_portal_required
def profissionais_ajax(request: HttpRequest) -> JsonResponse | HttpResponse:
    """AJAX: Lista profissionais disponíveis (throttle + TTL configurável)."""
    ensure_tenant_session(request)
    if check_throttle_auto(cast("int", request.user.id), "profissionais"):
        return _throttle_response(cast("int", request.user.id), "profissionais")
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        tenant = conta_cliente.cliente.tenant

        ttl = get_cache_ttl()
        data_cache_key = f"portal_prof_data_{tenant.id}"
        meta_cache_key = f"portal_prof_meta_{tenant.id}"
        cached = cache.get(data_cache_key)
        meta = cache.get(meta_cache_key)

        if not cached or not meta:
            profissionais_qs = Funcionario.objects.filter(
                tenant=tenant,
                ativo=True,
                tipo_funcionario="PROFISSIONAL",
            ).order_by("nome")
            profissionais_data = [
                {
                    "id": p.id,
                    "nome": p.nome,
                    "especialidade": (
                        getattr(p.departamento, "nome", None) if getattr(p, "departamento", None) else None
                    ),
                }
                for p in profissionais_qs
            ]
            agg = Funcionario.objects.filter(tenant=tenant, ativo=True, tipo_funcionario="PROFISSIONAL").aggregate(
                m=Max("updated_at"),
                c=Count("id"),
            )
            last_updated = agg["m"] or timezone.now()
            count = agg["c"] or 0
            etag = f'W/"prof-{tenant.id}-{int(last_updated.timestamp())}-{count}"'
            meta = {"etag": etag, "last_updated": last_updated, "count": count}
            cache.set(data_cache_key, profissionais_data, ttl)
            cache.set(meta_cache_key, meta, ttl)
            cached = profissionais_data

        client_etag = request.META.get("HTTP_IF_NONE_MATCH")
        if client_etag and meta["etag"] == client_etag:
            response = HttpResponse(status=304)
            response["ETag"] = meta["etag"]
            response["Cache-Control"] = f"private, max-age={ttl}"
            response["Last-Modified"] = http_date(meta["last_updated"].timestamp())
        else:
            response = JsonResponse({"success": True, "profissionais": cached})
            response["ETag"] = meta["etag"]
            response["Cache-Control"] = f"private, max-age={ttl}"
            response["Last-Modified"] = http_date(meta["last_updated"].timestamp())

    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    else:  # TRY300
        return response


@cliente_portal_required
def agendamento_status_ajax(request: HttpRequest, agendamento_id: int) -> JsonResponse:
    """AJAX: Status consolidado + flags de ação portal (Fase 2)."""
    ensure_tenant_session(request)
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        ag = Agendamento.objects.get(
            id=agendamento_id,
            cliente=conta_cliente.cliente,
            tenant=conta_cliente.cliente.tenant,
        )
        status_data = AtendimentoAgendamentoService.obter_status_integrado(ag.id)
        if not status_data:
            return JsonResponse({"success": False, "error": "Status indisponível"}, status=404)

        now = timezone.now()
        data_inicio = status_data["agendamento"]["data_inicio"]
        antecedencia = get_checkin_antecedencia_minutos()
        janela_inferior = data_inicio - timedelta(minutes=antecedencia)
        janela_superior = data_inicio + timedelta(minutes=get_checkin_tolerancia_pos_minutos())
        tolerancia_finalizacao_h = get_finalizacao_tolerancia_horas()
        limite_finalizacao = data_inicio + timedelta(hours=tolerancia_finalizacao_h)

        pode_checkin = status_data.get("pode_iniciar") and janela_inferior <= now <= janela_superior
        # Para finalização é necessário que algum atendimento esteja EM_ANDAMENTO
        esta_em_andamento = status_data.get("esta_em_andamento")
        pode_finalizar = esta_em_andamento and now <= limite_finalizacao
        # Avaliação: concluído e atendimento sem satisfação
        atendimentos = status_data.get("atendimentos", [])
        falta_avaliacao = any(at.get("satisfacao_cliente") is None for at in atendimentos)
        pode_avaliar = status_data.get("foi_concluido") and falta_avaliacao

        status_data.update(
            {
                "pode_checkin": bool(pode_checkin),
                "pode_finalizar": bool(pode_finalizar),
                "pode_avaliar": bool(pode_avaliar),
            },
        )
        return JsonResponse({"success": True, "status": status_data})
    except Agendamento.DoesNotExist:
        return JsonResponse({"success": False, "error": "Agendamento não encontrado"}, status=404)
    except (ValueError, PermissionDenied) as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def checkin_agendamento_ajax(request: HttpRequest, agendamento_id: int) -> JsonResponse:
    """AJAX: Realiza check-in do agendamento (POST)."""
    ensure_tenant_session(request)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método não permitido"}, status=405)
    # Usa escopo por agendamento para não bloquear outros agendamentos do mesmo usuário
    if check_throttle_auto(cast("int", request.user.id), "checkin", scope=agendamento_id):
        return _throttle_response(cast("int", request.user.id), "checkin", scope=agendamento_id)
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        atendimento = PortalClienteService.checkin_agendamento(conta_cliente, agendamento_id)
        inc_action("checkin", "success")
        inc_action_error_kind("checkin", "success")
        return JsonResponse({"success": True, "atendimento_id": atendimento.id})
    except (ValueError, PermissionDenied, Atendimento.DoesNotExist) as e:
        inc_action("checkin", "error")
        inc_action_error_kind("checkin", _classify_error_kind("checkin", e))
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def finalizar_atendimento_ajax(request: HttpRequest, atendimento_id: int) -> JsonResponse:
    """AJAX: Finaliza atendimento em andamento (POST)."""
    ensure_tenant_session(request)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método não permitido"}, status=405)
    if check_throttle_auto(cast("int", request.user.id), "finalizar"):
        return _throttle_response(cast("int", request.user.id), "finalizar")
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        atendimento = PortalClienteService.finalizar_atendimento(conta_cliente, atendimento_id)
        inc_action("finalizar", "success")
        inc_action_error_kind("finalizar", "success")
        return JsonResponse({"success": True, "atendimento_id": atendimento.id})
    except (ValueError, PermissionDenied, Atendimento.DoesNotExist) as e:
        inc_action("finalizar", "error")
        inc_action_error_kind("finalizar", _classify_error_kind("finalizar", e))
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def avaliar_atendimento_ajax(request: HttpRequest, atendimento_id: int) -> JsonResponse:
    """AJAX: Registra avaliação de satisfação (POST nota)."""
    ensure_tenant_session(request)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método não permitido"}, status=405)
    if check_throttle_auto(cast("int", request.user.id), "avaliar"):
        return _throttle_response(cast("int", request.user.id), "avaliar")
    try:
        nota_raw = request.POST.get("nota") or request.GET.get("nota")
        nota = int(nota_raw) if nota_raw is not None else None
        if nota is None:
            return JsonResponse({"success": False, "error": "Nota obrigatória"}, status=400)
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        atendimento = PortalClienteService.registrar_avaliacao(conta_cliente, atendimento_id, nota)
        inc_action("avaliar", "success")
        inc_action_error_kind("avaliar", "success")
        return JsonResponse({"success": True, "atendimento_id": atendimento.id, "nota": atendimento.satisfacao_cliente})
    except (ValueError, PermissionDenied, Atendimento.DoesNotExist) as e:
        inc_action("avaliar", "error")
        inc_action_error_kind("avaliar", _classify_error_kind("avaliar", e))
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:  # pragma: no cover  # noqa: BLE001
        inc_action("avaliar", "error")
        inc_action_error_kind("avaliar", _classify_error_kind("avaliar", e))
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def criar_agendamento_ajax(request: HttpRequest) -> JsonResponse:
    """AJAX: Cria agendamento para o cliente autenticado.

    Espera POST com: slot_id, servico_id, (opcional) observacoes.
    Retorna JSON com agendamento_id.
    """
    ensure_tenant_session(request)
    if request.method != "POST":  # Método estrito
        return JsonResponse({"success": False, "error": "Método não permitido"}, status=405)
    slot_id = request.POST.get("slot_id")
    servico_id = request.POST.get("servico_id")
    observacoes = request.POST.get("observacoes") or None
    if not slot_id or not servico_id:
        return JsonResponse({"success": False, "error": "Parâmetros obrigatórios ausentes"}, status=400)
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        ag = PortalClienteService.criar_agendamento_cliente(
            conta_cliente,
            slot_id=int(slot_id),
            servico_id=int(servico_id),
            observacoes=observacoes,
        )
        inc_action("criar_agendamento", "success")
        return JsonResponse({"success": True, "agendamento_id": ag.id})
    except (ValueError, PermissionDenied) as e:
        inc_action("criar_agendamento", "error")
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@cliente_portal_required
def cancelar_agendamento_ajax(request: HttpRequest, agendamento_id: int) -> JsonResponse:
    """AJAX: Cancela agendamento existente (se regras permitirem)."""
    ensure_tenant_session(request)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método não permitido"}, status=405)
    motivo = request.POST.get("motivo") or None
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        ag = PortalClienteService.cancelar_agendamento_cliente(conta_cliente, agendamento_id, motivo=motivo)
        inc_action("cancelar_agendamento", "success")
        return JsonResponse({"success": True, "agendamento_id": ag.id, "status": ag.status})
    except (ValueError, PermissionDenied) as e:
        inc_action("cancelar_agendamento", "error")
        return JsonResponse({"success": False, "error": str(e)}, status=400)

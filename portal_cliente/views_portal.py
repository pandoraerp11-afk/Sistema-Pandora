from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import http_date

from agendamentos.models import Agendamento
from funcionarios.models import Funcionario
from prontuarios.models import Atendimento, FotoEvolucao
from prontuarios.services import AtendimentoAgendamentoService
from servicos.models import Servico
from shared.portal.decorators import cliente_portal_required

from .metrics import PORTAL_CLIENTE_PAGE_HITS, track_action
from .repositories import FotoEvolucaoRepository
from .services import PortalClienteService


@cliente_portal_required
def dashboard(request):
    """Dashboard principal do cliente - Fase 1"""
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
def documentos_list(request):
    """Lista de documentos disponíveis"""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="documentos_list").inc()
    with track_action("render_documentos_list"):
        contas = request.contas_cliente
        return render(request, "portal_cliente/documentos_list.html", {"contas": contas})


# ===== AGENDAMENTOS - FASE 1 =====


@cliente_portal_required
def agendamentos_lista(request):
    """Lista agendamentos do cliente"""
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
def novo_agendamento(request):
    """Interface para criar novo agendamento"""
    PORTAL_CLIENTE_PAGE_HITS.labels(page="novo_agendamento").inc()

    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    if request.method == "POST":
        try:
            slot_id = request.POST.get("slot_id")
            # Novo nome definitivo: servico_id
            servico_id = request.POST.get("servico_id")
            observacoes = request.POST.get("observacoes", "").strip()

            if not slot_id or not servico_id:
                raise ValueError("Slot e serviço são obrigatórios")

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

        except Exception as e:
            messages.error(request, f"Erro ao criar agendamento: {str(e)}")

    # Buscar serviços clínicos disponíveis
    servicos = Servico.objects.filter(tenant=conta_cliente.cliente.tenant, ativo=True, is_clinical=True).order_by(
        "nome_servico"
    )

    # Buscar profissionais disponíveis
    profissionais = Funcionario.objects.filter(
        tenant=conta_cliente.cliente.tenant, ativo=True, tipo_funcionario="PROFISSIONAL"
    ).order_by("nome")

    context = {
        "conta_cliente": conta_cliente,
        "servicos": servicos,
        "profissionais": profissionais,
    }
    return render(request, "portal_cliente/novo_agendamento.html", context)


@cliente_portal_required
def cancelar_agendamento(request, agendamento_id):
    """Cancelar agendamento existente"""
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    if request.method == "POST":
        try:
            motivo = request.POST.get("motivo", "").strip()

            agendamento = PortalClienteService.cancelar_agendamento_cliente(
                conta_cliente=conta_cliente, agendamento_id=agendamento_id, motivo=motivo if motivo else None
            )

            messages.success(request, "Agendamento cancelado com sucesso!")
            return redirect("portal_cliente:agendamentos_lista")

        except Exception as e:
            messages.error(request, f"Erro ao cancelar agendamento: {str(e)}")
            return redirect("portal_cliente:agendamentos_lista")

    # Verificar se pode cancelar
    pode_cancelar, erro = PortalClienteService.pode_cancelar_agendamento(conta_cliente, agendamento_id)

    if not pode_cancelar:
        messages.error(request, erro)
        return redirect("portal_cliente:agendamentos_lista")

    # Buscar agendamento para confirmação
    agendamento = get_object_or_404(
        Agendamento, id=agendamento_id, cliente=conta_cliente.cliente, tenant=conta_cliente.cliente.tenant
    )

    context = {
        "conta_cliente": conta_cliente,
        "agendamento": agendamento,
    }
    return render(request, "portal_cliente/cancelar_agendamento.html", context)


# ===== HISTÓRICO DE ATENDIMENTOS - FASE 1 =====


@cliente_portal_required
def historico_atendimentos(request):
    """Histórico seguro de atendimentos (sem dados sensíveis)"""
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
def detalhe_atendimento(request, atendimento_id):
    """Detalhe seguro de um atendimento específico"""
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
def galeria_fotos(request):
    """Galeria de fotos com thumbnails (nunca originais)"""
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
def visualizar_foto(request, foto_id):
    """Visualização de foto individual (apenas thumbnail/webp)"""
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
        raise Http404("Imagem não disponível")

    context = {
        "conta_cliente": conta_cliente,
        "foto": foto,
    }
    return render(request, "portal_cliente/visualizar_foto.html", context)


# ===== ENDPOINTS AJAX - FASE 1 =====


@login_required
def slots_disponiveis_ajax(request):
    """AJAX: Buscar slots disponíveis para agendamento"""
    # Throttling simples: máximo 20 chamadas / 60s por usuário
    cache_key = f"portal_slots_req_{request.user.id}"
    reqs = cache.get(cache_key, 0)
    if reqs > 20:
        return JsonResponse(
            {"success": False, "error": "Limite de requisições atingido. Tente novamente em instantes."}, status=429
        )
    cache.incr(cache_key) if cache.get(cache_key) else cache.set(cache_key, 1, 60)
    conta_cliente = PortalClienteService.get_conta_ativa(request.user)

    # Parâmetros de filtro
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    servico_id = request.GET.get("servico_id")
    profissional_id = request.GET.get("profissional_id")

    try:
        # Converter datas se fornecidas
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        if data_fim:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d")

        slots = PortalClienteService.listar_slots_disponiveis(
            conta_cliente=conta_cliente,
            data_inicio=data_inicio,
            data_fim=data_fim,
            servico_id=int(servico_id) if servico_id else None,
            profissional_id=int(profissional_id) if profissional_id else None,
        )

        slots_data = [
            {
                "id": slot.id,
                "horario": slot.horario.isoformat(),
                "horario_display": slot.horario.strftime("%d/%m/%Y às %H:%M"),
                "profissional": slot.profissional.nome,
                "profissional_id": slot.profissional.id,
                "capacidade_disponivel": slot.capacidade_total - slot.capacidade_utilizada,
            }
            for slot in slots
        ]
        return JsonResponse({"success": True, "slots": slots_data})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def servicos_ajax(request):
    """AJAX: Lista serviços clínicos disponíveis"""
    cache_key = f"portal_serv_req_{request.user.id}"
    reqs = cache.get(cache_key, 0)
    if reqs > 30:
        return JsonResponse({"success": False, "error": "Limite de requisições atingido."}, status=429)
    cache.incr(cache_key) if cache.get(cache_key) else cache.set(cache_key, 1, 60)
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        tenant = conta_cliente.cliente.tenant

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
            servicos_data = []
            for proc in servicos_qs:
                perfil = getattr(proc, "perfil_clinico", None)
                servicos_data.append(
                    {
                        "id": proc.id,
                        "nome": proc.nome_servico,  # chave legado 'nome'
                        "descricao": proc.descricao_curta or proc.descricao,
                        "duracao_estimada": str(getattr(perfil, "duracao_estimada", "")) if perfil else None,
                        "valor_base": float(proc.preco_base) if proc.preco_base is not None else None,
                    }
                )
            # Metadados para ETag
            agg = Servico.objects.filter(tenant=tenant, ativo=True, is_clinical=True).aggregate(
                m=Max("ultima_atualizacao"), c=Count("id")
            )
            last_updated = agg["m"] or timezone.now()
            count = agg["c"] or 0
            etag = f'W/"servico-{tenant.id}-{int(last_updated.timestamp())}-{count}"'
            meta = {"etag": etag, "last_updated": last_updated, "count": count}
            cache.set(data_cache_key, servicos_data, 60)
            cache.set(meta_cache_key, meta, 60)
            cached = servicos_data

        # Resposta condicional
        client_etag = request.META.get("HTTP_IF_NONE_MATCH")
        if client_etag and meta["etag"] == client_etag:
            resp304 = HttpResponse(status=304)
            resp304["ETag"] = meta["etag"]
            resp304["Cache-Control"] = "private, max-age=60"
            resp304["Last-Modified"] = http_date(meta["last_updated"].timestamp())
            return resp304

        response = JsonResponse({"success": True, "servicos": cached})
        response["ETag"] = meta["etag"]
        response["Cache-Control"] = "private, max-age=60"
        response["Last-Modified"] = http_date(meta["last_updated"].timestamp())
        return response
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def profissionais_ajax(request):
    """AJAX: Lista profissionais disponíveis"""
    cache_key = f"portal_prof_req_{request.user.id}"
    reqs = cache.get(cache_key, 0)
    if reqs > 30:
        return JsonResponse({"success": False, "error": "Limite de requisições atingido."}, status=429)
    cache.incr(cache_key) if cache.get(cache_key) else cache.set(cache_key, 1, 60)
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        tenant = conta_cliente.cliente.tenant

        data_cache_key = f"portal_prof_data_{tenant.id}"
        meta_cache_key = f"portal_prof_meta_{tenant.id}"
        cached = cache.get(data_cache_key)
        meta = cache.get(meta_cache_key)

        if not cached or not meta:
            profissionais_qs = Funcionario.objects.filter(
                tenant=tenant, ativo=True, tipo_funcionario="PROFISSIONAL"
            ).order_by("nome")
            profissionais_data = []
            for prof in profissionais_qs:
                profissionais_data.append(
                    {
                        "id": prof.id,
                        "nome": prof.nome,
                        "especialidade": getattr(prof.departamento, "nome", None)
                        if getattr(prof, "departamento", None)
                        else None,
                    }
                )
            agg = Funcionario.objects.filter(tenant=tenant, ativo=True, tipo_funcionario="PROFISSIONAL").aggregate(
                m=Max("updated_at"), c=Count("id")
            )
            last_updated = agg["m"] or timezone.now()
            count = agg["c"] or 0
            etag = f'W/"prof-{tenant.id}-{int(last_updated.timestamp())}-{count}"'
            meta = {"etag": etag, "last_updated": last_updated, "count": count}
            cache.set(data_cache_key, profissionais_data, 60)
            cache.set(meta_cache_key, meta, 60)
            cached = profissionais_data

        client_etag = request.META.get("HTTP_IF_NONE_MATCH")
        if client_etag and meta["etag"] == client_etag:
            resp304 = HttpResponse(status=304)
            resp304["ETag"] = meta["etag"]
            resp304["Cache-Control"] = "private, max-age=60"
            resp304["Last-Modified"] = http_date(meta["last_updated"].timestamp())
            return resp304

        response = JsonResponse({"success": True, "profissionais": cached})
        response["ETag"] = meta["etag"]
        response["Cache-Control"] = "private, max-age=60"
        response["Last-Modified"] = http_date(meta["last_updated"].timestamp())
        return response

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def agendamento_status_ajax(request, agendamento_id):
    """AJAX: Status consolidado (agendamento + atendimentos)"""
    try:
        conta_cliente = PortalClienteService.get_conta_ativa(request.user)
        # Garantir que o agendamento pertence ao cliente
        ag = Agendamento.objects.get(
            id=agendamento_id, cliente=conta_cliente.cliente, tenant=conta_cliente.cliente.tenant
        )
        status_data = AtendimentoAgendamentoService.obter_status_integrado(ag.id)
        return JsonResponse({"success": True, "status": status_data})
    except Agendamento.DoesNotExist:
        return JsonResponse({"success": False, "error": "Agendamento não encontrado"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

# agenda/views.py
import calendar
import contextlib
import json
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import TenantRequiredMixin
from core.utils import get_current_tenant

from .forms import EventoBuscaForm, EventoCalendarioForm, EventoForm
from .models import Evento, EventoLembrete, LogEvento


class AgendaMixin(LoginRequiredMixin, TenantRequiredMixin):
    """Mixin base para views de agenda"""

    model = Evento

    def get_queryset(self):
        """Filtra eventos por tenant"""
        queryset = super().get_queryset()
        tenant = get_current_tenant(self.request)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenant"] = get_current_tenant(self.request)
        return context


@login_required
def agenda_home(request):
    """Dashboard principal do módulo agenda"""
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Queryset base para estatísticas
    eventos_qs = Evento.objects.filter(tenant=tenant) if tenant else Evento.objects.all()

    # Data atual e períodos
    hoje = timezone.now().date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    inicio_mes = hoje.replace(day=1)
    proximo_mes = (inicio_mes + timedelta(days=32)).replace(day=1)
    fim_mes = proximo_mes - timedelta(days=1)

    # Estatísticas principais
    total_eventos = eventos_qs.count()
    eventos_hoje = eventos_qs.filter(data_inicio__date=hoje).count()
    eventos_semana = eventos_qs.filter(data_inicio__date__gte=inicio_semana, data_inicio__date__lte=fim_semana).count()
    eventos_mes = eventos_qs.filter(data_inicio__date__gte=inicio_mes, data_inicio__date__lte=fim_mes).count()

    # Estatísticas por status
    eventos_pendentes = eventos_qs.filter(status="pendente").count()
    eventos_realizados = eventos_qs.filter(status__in=["realizado", "concluido"]).count()
    eventos_cancelados = eventos_qs.filter(status="cancelado").count()

    # Estatísticas por prioridade
    eventos_alta_prioridade = eventos_qs.filter(prioridade="alta").count()
    eventos_media_prioridade = eventos_qs.filter(prioridade="media").count()
    eventos_baixa_prioridade = eventos_qs.filter(prioridade="baixa").count()

    # Próximos eventos (próximos 7 dias)
    proximos_7_dias = hoje + timedelta(days=7)
    proximos_eventos = eventos_qs.filter(
        data_inicio__date__gte=hoje, data_inicio__date__lte=proximos_7_dias, status="pendente"
    ).order_by("data_inicio")[:10]

    # Eventos recentes (últimos 7 dias)
    ultimos_7_dias = hoje - timedelta(days=7)
    eventos_recentes = eventos_qs.filter(data_inicio__date__gte=ultimos_7_dias, data_inicio__date__lte=hoje).order_by(
        "-data_inicio"
    )[:5]

    # Top usuários por eventos (responsáveis mais ativos)
    top_responsaveis = (
        eventos_qs.filter(responsavel__isnull=False)
        .values("responsavel__first_name", "responsavel__last_name")
        .annotate(total_eventos=Count("id"))
        .order_by("-total_eventos")[:5]
    )

    # Estatísticas de conclusão
    if total_eventos > 0:
        taxa_conclusao = round((eventos_realizados / total_eventos) * 100, 1)
        taxa_cancelamento = round((eventos_cancelados / total_eventos) * 100, 1)
    else:
        taxa_conclusao = 0
        taxa_cancelamento = 0

    # Dados para gráficos
    eventos_por_status = [
        {"status": "Pendente", "count": eventos_pendentes, "color": "#ffc107"},
        {"status": "Realizado/Concluído", "count": eventos_realizados, "color": "#28a745"},
        {"status": "Cancelado", "count": eventos_cancelados, "color": "#dc3545"},
    ]

    eventos_por_prioridade = [
        {"prioridade": "Alta", "count": eventos_alta_prioridade, "color": "#dc3545"},
        {"prioridade": "Média", "count": eventos_media_prioridade, "color": "#ffc107"},
        {"prioridade": "Baixa", "count": eventos_baixa_prioridade, "color": "#28a745"},
    ]

    context = {
        "titulo": "Agenda",
        "subtitulo": "Acompanhe e controle seus compromissos",
        "tenant": tenant,
        # Estatísticas principais
        "total_eventos": total_eventos,
        "eventos_hoje": eventos_hoje,
        "eventos_semana": eventos_semana,
        "eventos_mes": eventos_mes,
        "eventos_pendentes": eventos_pendentes,
        "eventos_realizados": eventos_realizados,
        "eventos_cancelados": eventos_cancelados,
        "eventos_alta_prioridade": eventos_alta_prioridade,
        "taxa_conclusao": taxa_conclusao,
        "taxa_cancelamento": taxa_cancelamento,
        # Listas
        "proximos_eventos": proximos_eventos,
        "eventos_recentes": eventos_recentes,
        "top_responsaveis": top_responsaveis,
        # Dados para gráficos
        "eventos_por_status": eventos_por_status,
        "eventos_por_prioridade": eventos_por_prioridade,
    }

    return render(request, "agenda/agenda_home.html", context)


class EventoListView(AgendaMixin, ListView):
    """View para listagem de eventos"""

    template_name = "agenda/evento_list.html"
    context_object_name = "eventos"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtros de busca
        search = self.request.GET.get("search", "")
        status = self.request.GET.get("status", "")
        prioridade = self.request.GET.get("prioridade", "")
        responsavel = self.request.GET.get("responsavel", "")
        data_inicio = self.request.GET.get("data_inicio", "")
        data_fim = self.request.GET.get("data_fim", "")

        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search) | Q(descricao__icontains=search) | Q(local__icontains=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        if prioridade:
            queryset = queryset.filter(prioridade=prioridade)

        if responsavel:
            queryset = queryset.filter(responsavel_id=responsavel)

        if data_inicio:
            queryset = queryset.filter(data_inicio__date__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data_inicio__date__lte=data_fim)

        return queryset.order_by("-data_inicio")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eventos = self.get_queryset()
        tenant = get_current_tenant(self.request)

        # Estatísticas para cards
        hoje = timezone.now().date()

        context.update(
            {
                "titulo": "Eventos",
                "subtitulo": "Gerenciamento de eventos da agenda",
                "add_url": reverse("agenda:evento_create"),
                "module": "agenda",
                # Formulário de busca
                "form_busca": EventoBuscaForm(data=self.request.GET, tenant=tenant),
                # Estatísticas
                "total_count": eventos.count(),
                "eventos_hoje": eventos.filter(data_inicio__date=hoje).count(),
                "eventos_pendentes": eventos.filter(status="pendente").count(),
                "eventos_realizados": eventos.filter(status="realizado").count(),
            }
        )

        return context


class EventoCreateView(AgendaMixin, CreateView):
    """View para criação de eventos"""

    form_class = EventoForm
    template_name = "agenda/evento_form.html"
    success_url = reverse_lazy("agenda:evento_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "titulo": "Novo Evento",
                "subtitulo": "Cadastrar novo evento na agenda",
                "module": "agenda",
            }
        )
        # Integração: se vindo de uma conversa do chat, mostrar dica
        conversa_id = self.request.GET.get("conversa_id")
        if conversa_id:
            context["conversa_origem_id"] = conversa_id
            context["subtitulo"] = "Agendar reunião a partir do chat"
        return context

    def form_valid(self, form):
        # Definir tenant
        tenant = get_current_tenant(self.request)
        if tenant:
            form.instance.tenant = tenant

        # Se não há responsável definido, usar o usuário atual
        if not form.instance.responsavel:
            form.instance.responsavel = self.request.user

        # Pré-preenchimento de participantes a partir de conversa do chat
        conversa_id = self.request.GET.get("conversa_id")
        if conversa_id:
            try:
                from chat.models import Conversa

                conversa = Conversa.objects.get(id=conversa_id)
                # Adicionar participantes da conversa ao evento
                participantes_ids = list(conversa.participantes.values_list("id", flat=True))
            except Exception:
                participantes_ids = []
        else:
            participantes_ids = []

        response = super().form_valid(form)

        # Se havia conversa, vincular participantes após salvar
        if participantes_ids:
            with contextlib.suppress(Exception):
                self.object.participantes.add(*participantes_ids)

        # Lembretes padrão após salvar evento
        self._aplicar_lembretes_padrao(form)

        # Mensagem de sistema no chat vinculando ao evento criado
        if conversa_id:
            try:
                from chat.models import Conversa, Mensagem

                conversa = Conversa.objects.get(id=conversa_id)
                url = reverse("agenda:evento_detail", args=[self.object.id])
                Mensagem.objects.create(
                    tenant=self.object.tenant,
                    conversa=conversa,
                    remetente=self.request.user,
                    conteudo=f"Reunião agendada: {self.object.titulo} – veja os detalhes em {url}",
                    tipo="sistema",
                )
            except Exception:
                pass

        messages.success(self.request, "Evento criado com sucesso!")
        return response

    # Método reutilizável também chamado pelo UpdateView
    def _aplicar_lembretes_padrao(self, form):  # compat: mantido no CreateView para não quebrar referências
        aplicar_lembretes_padrao(self.object, form.cleaned_data)


class EventoUpdateView(AgendaMixin, UpdateView):
    """View para edição de eventos"""

    form_class = EventoForm
    template_name = "agenda/evento_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "titulo": f"Editar Evento: {self.object.titulo}",
                "subtitulo": "Editar dados do evento",
                "module": "agenda",
                "evento": self.object,
            }
        )
        return context

    def get_success_url(self):
        return reverse("agenda:evento_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        aplicar_lembretes_padrao(self.object, form.cleaned_data)
        messages.success(self.request, "Evento atualizado com sucesso!")
        return response


# ------------------------------------------------------------------
# Função util compartilhada para aplicação de lembretes (Create/Update)
# ------------------------------------------------------------------
def aplicar_lembretes_padrao(evento, cleaned_data):
    try:
        from .models import AgendaConfiguracao

        tenant = evento.tenant
        lembrete_15 = cleaned_data.get("lembrete_15")
        lembrete_60 = cleaned_data.get("lembrete_60")

        minutos_set = set()
        if lembrete_15:
            minutos_set.add(15)
        if lembrete_60:
            minutos_set.add(60)
        try:
            cfg = tenant.agenda_config
            for m in cfg.lembretes_padrao:
                try:
                    minutos_set.add(int(m))
                except Exception:
                    continue
        except AgendaConfiguracao.DoesNotExist:
            minutos_set.update({15, 60})

        usuarios = set()
        if evento.responsavel_id:
            usuarios.add(evento.responsavel_id)
        with contextlib.suppress(Exception):
            usuarios.update(list(evento.participantes.values_list("id", flat=True)))

        def set_lembrete(uid, minutos, ativo):
            try:
                obj, _ = EventoLembrete.objects.get_or_create(evento=evento, usuario_id=uid, minutos_antes=minutos)
                if obj.ativo != ativo:
                    obj.ativo = ativo
                    obj.save(update_fields=["ativo"])
            except Exception:
                pass

        for uid in usuarios:
            for minutos in minutos_set:
                set_lembrete(uid, minutos, True)
            try:
                existentes = EventoLembrete.objects.filter(evento=evento, usuario_id=uid)
                for lemb in existentes:
                    if lemb.minutos_antes not in minutos_set and lemb.ativo:
                        lemb.ativo = False
                        lemb.save(update_fields=["ativo"])
            except Exception:
                pass
    except Exception:
        # Silencia totalmente erros de lembretes para não quebrar fluxo principal
        pass


class EventoDetailView(AgendaMixin, DetailView):
    """View para detalhes do evento"""

    template_name = "agenda/evento_detail.html"
    context_object_name = "evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evento = self.object

        # Logs do evento
        logs = LogEvento.objects.filter(evento=evento).order_by("-data_hora")[:10]

        # Verificar se o usuário pode editar
        user = self.request.user
        pode_editar = user.is_superuser or user == evento.responsavel or user in evento.participantes.all()

        context.update(
            {
                "titulo": f"Evento: {evento.titulo}",
                "subtitulo": "Detalhes do evento",
                "logs": logs,
                "pode_editar": pode_editar,
                "lembretes_participantes": evento.lembretes.select_related("usuario").order_by(
                    "usuario__first_name", "minutos_antes"
                ),
            }
        )

        return context


class EventoDeleteView(AgendaMixin, DeleteView):
    """View para exclusão de eventos"""

    template_name = "agenda/evento_confirm_delete.html"
    success_url = reverse_lazy("agenda:evento_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Evento excluído com sucesso!")
        return super().delete(request, *args, **kwargs)


@login_required
def gerenciar_lembrete_participante(request, pk):
    """Cria/ativa/desativa lembretes individuais para um participante via POST."""
    evento = get_object_or_404(Evento, pk=pk)
    tenant = get_current_tenant(request)
    if evento.tenant != tenant and not request.user.is_superuser:
        return HttpResponseForbidden("Acesso negado")

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)

    user_id = request.POST.get("user_id")
    minutos = int(request.POST.get("minutos", "15") or 15)
    ativo_flag = request.POST.get("ativo", "true").lower() in ("1", "true", "on")

    # Permissão: responsável ou superuser pode ajustar; o próprio usuário pode ajustar o seu
    if not (request.user.is_superuser or request.user == evento.responsavel or str(request.user.id) == str(user_id)):
        return HttpResponseForbidden("Sem permissão")

    try:
        lemb, created = EventoLembrete.objects.get_or_create(evento=evento, usuario_id=user_id, minutos_antes=minutos)
        if lemb.ativo != ativo_flag:
            lemb.ativo = ativo_flag
            lemb.save(update_fields=["ativo"])
        return JsonResponse({"ok": True, "created": created, "ativo": lemb.ativo})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


@login_required
def agenda_calendar(request):
    """View para visualização em calendário"""
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa."))
        return redirect("core:tenant_select")

    # Parâmetros do calendário
    year = int(request.GET.get("year", timezone.now().year))
    month = int(request.GET.get("month", timezone.now().month))

    # Criar datas para o mês
    primeiro_dia = date(year, month, 1)
    if month == 12:
        ultimo_dia = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = date(year, month + 1, 1) - timedelta(days=1)

    # Buscar eventos do mês
    eventos = Evento.objects.filter(
        tenant=tenant, data_inicio__date__gte=primeiro_dia, data_inicio__date__lte=ultimo_dia
    ).order_by("data_inicio")

    # Organizar eventos por dia
    eventos_por_dia = {}
    for evento in eventos:
        dia = evento.data_inicio.date().day
        if dia not in eventos_por_dia:
            eventos_por_dia[dia] = []
        eventos_por_dia[dia].append(evento)

    # Gerar calendário
    cal = calendar.monthcalendar(year, month)

    # Navegação
    mes_anterior = month - 1 if month > 1 else 12
    ano_anterior = year if month > 1 else year - 1
    mes_proximo = month + 1 if month < 12 else 1
    ano_proximo = year if month < 12 else year + 1

    context = {
        "titulo": "Calendário",
        "subtitulo": f"{calendar.month_name[month]} {year}",
        "tenant": tenant,
        "calendar": cal,
        "eventos_por_dia": eventos_por_dia,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "mes_anterior": mes_anterior,
        "ano_anterior": ano_anterior,
        "mes_proximo": mes_proximo,
        "ano_proximo": ano_proximo,
        "form_evento": EventoCalendarioForm(tenant=tenant),
    }

    return render(request, "agenda/agenda_calendar.html", context)


# Views AJAX
@login_required
@csrf_exempt
def evento_ajax_create(request):
    """Criar evento via AJAX (para calendário)"""
    if request.method == "POST":
        data = json.loads(request.body)
        tenant = get_current_tenant(request)

        try:
            evento = Evento.objects.create(
                tenant=tenant,
                titulo=data.get("titulo", ""),
                descricao=data.get("descricao", ""),
                data_inicio=datetime.fromisoformat(data.get("data_inicio")),
                data_fim=datetime.fromisoformat(data.get("data_fim")) if data.get("data_fim") else None,
                dia_inteiro=data.get("dia_inteiro", False),
                prioridade=data.get("prioridade", "media"),
                local=data.get("local", ""),
                responsavel=request.user,
            )

            return JsonResponse({"success": True, "evento_id": evento.id, "message": "Evento criado com sucesso!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Erro ao criar evento: {str(e)}"})

    return JsonResponse({"success": False, "message": "Método não permitido"})


@login_required
def evento_ajax_update_status(request, pk):
    """Atualizar status do evento via AJAX"""
    if request.method == "POST":
        evento = get_object_or_404(Evento, pk=pk)
        tenant = get_current_tenant(request)

        if evento.tenant != tenant:
            return JsonResponse({"success": False, "message": "Não autorizado"})

        novo_status = request.POST.get("status")
        if novo_status in ["pendente", "realizado", "cancelado"]:
            evento.status = novo_status
            evento.save()

            return JsonResponse({"success": True, "message": f"Status atualizado para {evento.get_status_display()}"})

    return JsonResponse({"success": False, "message": "Erro ao atualizar status"})


@login_required
def evento_search_ajax(request):
    """Busca AJAX para eventos"""
    term = request.GET.get("term", "")
    tenant = get_current_tenant(request)

    eventos_qs = Evento.objects.filter(tenant=tenant)

    if term:
        eventos_qs = eventos_qs.filter(
            Q(titulo__icontains=term) | Q(descricao__icontains=term) | Q(local__icontains=term)
        )

    results = []
    for evento in eventos_qs[:10]:
        results.append(
            {
                "id": evento.id,
                "text": evento.titulo,
                "data": evento.data_inicio.strftime("%d/%m/%Y %H:%M"),
                "status": evento.get_status_display(),
            }
        )

    return JsonResponse({"results": results})


@login_required
def api_eventos(request):
    """Endpoint JSON para FullCalendar listar eventos do tenant atual."""
    tenant = get_current_tenant(request)
    if not tenant and not request.user.is_superuser:
        return JsonResponse({"events": []})

    qs = Evento.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)

    # Filtros opcionais por período (ISO 8601)
    start = request.GET.get("start")
    end = request.GET.get("end")
    try:
        if start:
            qs = qs.filter(data_inicio__gte=datetime.fromisoformat(start))
        if end:
            qs = qs.filter(data_inicio__lte=datetime.fromisoformat(end))
    except Exception:
        # Ignora filtros inválidos
        pass

    events = []
    for e in qs:
        events.append(
            {
                "id": e.id,
                "title": e.titulo,
                "start": e.data_inicio.isoformat() if e.data_inicio else None,
                "end": e.data_fim.isoformat() if e.data_fim else None,
                "allDay": bool(e.dia_inteiro),
                "url": reverse("agenda:evento_detail", kwargs={"pk": e.pk}),
                "extendedProps": {
                    "status": e.status,
                    "prioridade": e.prioridade,
                    "description": e.descricao,
                    "local": getattr(e, "local", ""),
                    "responsavel": f"{e.responsavel.first_name} {e.responsavel.last_name}" if e.responsavel else "",
                    "tipo_evento": getattr(e, "tipo_evento", ""),
                },
            }
        )

    return JsonResponse(events, safe=False)


# Views de relatórios
@login_required
def eventos_relatorio(request):
    """Relatório de eventos"""
    tenant = get_current_tenant(request)

    if not tenant:
        return redirect("core:tenant_select")

    # Filtros
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    status = request.GET.get("status")
    responsavel = request.GET.get("responsavel")

    eventos = Evento.objects.filter(tenant=tenant)

    if data_inicio:
        eventos = eventos.filter(data_inicio__date__gte=data_inicio)
    if data_fim:
        eventos = eventos.filter(data_inicio__date__lte=data_fim)
    if status:
        eventos = eventos.filter(status=status)
    if responsavel:
        eventos = eventos.filter(responsavel_id=responsavel)

    context = {
        "titulo": "Relatório de Eventos",
        "eventos": eventos.order_by("-data_inicio"),
        "total_eventos": eventos.count(),
        "eventos_realizados": eventos.filter(status="realizado").count(),
        "eventos_cancelados": eventos.filter(status="cancelado").count(),
    }

    return render(request, "agenda/eventos_relatorio.html", context)


# Views funcionais (legacy)
def evento_list(request):
    """View funcional para listagem (legacy)"""
    return EventoListView.as_view()(request)


def evento_add(request):
    """View funcional para criação (legacy)"""
    return EventoCreateView.as_view()(request)


def evento_edit(request, pk):
    """View funcional para edição (legacy)"""
    return EventoUpdateView.as_view()(request, pk=pk)


def evento_detail(request, pk):
    """View funcional para detalhes (legacy)"""
    return EventoDetailView.as_view()(request, pk=pk)


def evento_delete(request, pk):
    """View funcional para exclusão (legacy)"""
    return EventoDeleteView.as_view()(request, pk=pk)

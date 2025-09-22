from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import generic

from .forms import AgendamentoForm, DisponibilidadeForm, ReagendarForm
from .models import STATUS_AGENDAMENTO, Agendamento, AuditoriaAgendamento, Disponibilidade, Slot, WaitlistEntry
from .services import AgendamentoService, SlotService


class TenantMixin:
    """Mixin simples para obter tenant do request (assumindo request.user.tenant)."""

    def get_tenant(self):  # pragma: no cover - dependente de auth
        user = getattr(self.request, "user", None)
        return getattr(user, "tenant", None)


def agendamento_home_view(request):  # pragma: no cover - UI
    today = timezone.localdate()
    tenant = getattr(request.user, "tenant", None)
    qs = Agendamento.objects.filter(tenant=tenant)
    futuros = qs.filter(data_inicio__gte=timezone.now())
    confirmados_futuros = futuros.filter(status="CONFIRMADO").count()
    pendentes_futuros = futuros.filter(status="PENDENTE").count()
    total_agendamentos = qs.count()
    semana_ini = today - timezone.timedelta(days=today.weekday())
    agendamentos_semana = qs.filter(data_inicio__date__gte=semana_ini).count()
    no_show_total = qs.filter(status="NO_SHOW").count()
    confirmados_hoje = qs.filter(status="CONFIRMADO", data_inicio__date=today).count()
    pendentes_hoje = qs.filter(status="PENDENTE", data_inicio__date=today).count()
    proximos_agendamentos = futuros.order_by("data_inicio")[:10]
    from collections import Counter

    status_counts = Counter(qs.filter(data_inicio__date=today).values_list("status", flat=True))
    taxa_no_show = (no_show_total / total_agendamentos * 100) if total_agendamentos else 0
    ctx = {
        "total_agendamentos": total_agendamentos,
        "agendamentos_semana": agendamentos_semana,
        "confirmados_futuros": confirmados_futuros,
        "pendentes_futuros": pendentes_futuros,
        "no_show_total": no_show_total,
        "taxa_no_show": taxa_no_show,
        "confirmados_hoje": confirmados_hoje,
        "pendentes_hoje": pendentes_hoje,
        "proximos_agendamentos": proximos_agendamentos,
        "status_hoje": dict(status_counts),
        "CLIENT_PORTAL_URL": getattr(settings, "CLIENT_PORTAL_URL", None),
    }
    return render(request, "agendamentos/agendamento_home.html", ctx)


class AgendamentoListView(TenantMixin, generic.ListView):
    template_name = "agendamentos/agendamento_list.html"
    model = Agendamento
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Agendamento.objects.select_related("cliente", "profissional")
            .filter(tenant=self.get_tenant())
            .order_by("-data_inicio")
        )
        data = self.request.GET.get("data")
        if data:
            qs = qs.filter(data_inicio__date=data)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(cliente__nome__icontains=q) | Q(servico__nome_servico__icontains=q))
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        servico = self.request.GET.get("servico")
        if servico:
            qs = qs.filter(servico_id=servico)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Contexto legado + novo layout ultra modern
        ctx["status_choices"] = STATUS_AGENDAMENTO
        from servicos.models import Servico

        ctx["servicos"] = Servico.objects.filter(tenant=self.get_tenant(), ativo=True, is_clinical=True).order_by(
            "nome_servico"
        )
        full_qs = self.get_queryset()
        total = full_qs.count()
        ctx["statistics"] = [
            {"label": "Total", "value": total, "icon": "fas fa-database", "color": "primary"},
            {
                "label": "Confirmados",
                "value": full_qs.filter(status="CONFIRMADO").count(),
                "icon": "fas fa-check-circle",
                "color": "success",
            },
            {
                "label": "Pendentes",
                "value": full_qs.filter(status="PENDENTE").count(),
                "icon": "fas fa-hourglass-half",
                "color": "warning",
            },
            {
                "label": "No-Show",
                "value": full_qs.filter(status="NO_SHOW").count(),
                "icon": "fas fa-user-slash",
                "color": "danger",
            },
        ]
        ctx["dashboard_url"] = reverse("agendamentos:dashboard")
        # Campos para template pandora_list_ultra_modern.html
        ctx["page_title"] = "Agendamentos"
        ctx["page_subtitle"] = "Gerencie agendamentos e status"
        # Configuração de colunas (mantendo sem alterar lógica de negócios)
        ctx["table_columns"] = [
            {"field": "id", "label": "ID", "width": "60"},
            {"field": "data_inicio", "label": "Início"},
            {"field": "profissional", "label": "Profissional"},
            {"field": "servico", "label": "Serviço"},
            {"field": "cliente", "label": "Cliente"},
            {"field": "status", "label": "Status"},
        ]
        # Ações (visualizar)
        ctx["actions"] = [
            {
                "url": reverse("agendamentos:agendamento-detail", args=[0]).replace("/0/", "/{id}/"),
                "icon": "fas fa-eye",
                "title": "Ver",
                "class": "btn-outline-primary",
            }
        ]
        # Ajuste de ordering dinâmico (não interfere na lógica de query principal)
        ordering = self.request.GET.get("ordering")
        if ordering:
            try:
                if ordering.startswith("-"):
                    ctx["object_list"] = ctx["object_list"].order_by(ordering)
                else:
                    ctx["object_list"] = ctx["object_list"].order_by(ordering)
            except Exception:  # pragma: no cover - defensivo
                pass
        return ctx

    # Mantém compatibilidade de template antigo se testes esperarem conteúdo textual direto


class AgendamentoDetailView(TenantMixin, generic.DetailView):
    template_name = "agendamentos/agendamento_detail.html"
    model = Agendamento

    def get_queryset(self):
        return Agendamento.objects.select_related("cliente", "profissional").filter(tenant=self.get_tenant())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["auditorias"] = self.object.auditoria.all()[:50]
        return ctx


class AgendamentoCreateView(TenantMixin, generic.CreateView):
    template_name = "agendamentos/agendamento_form.html"
    form_class = AgendamentoForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["tenant"] = self.get_tenant()
        return kw

    def form_valid(self, form):
        ag = form.save(commit=False)
        ag.tenant = self.get_tenant()
        try:
            ag = AgendamentoService.criar(
                tenant=ag.tenant,
                cliente=ag.cliente,
                profissional=ag.profissional,
                slot=form.cleaned_data.get("slot"),
                data_inicio=ag.data_inicio,
                data_fim=ag.data_fim,
                origem=ag.origem,
                servico=getattr(ag, "servico_id", None),
                user=self.request.user,
            )
            messages.success(self.request, f"Agendamento #{ag.id} criado.")
            return redirect("agendamentos:agendamento-detail", pk=ag.id)
        except Exception as e:  # pragma: no cover - fluxo UI
            form.add_error(None, str(e))
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["basic_fields"] = ["cliente", "profissional", "origem"]
        ctx["time_fields"] = ["slot", "data_inicio", "data_fim"]
        ctx["REQUIRE_SERVICO"] = getattr(settings, "REQUIRE_SERVICO", False)
        ctx["agendamento"] = None
        return ctx


class AgendamentoUpdateView(TenantMixin, generic.UpdateView):
    template_name = "agendamentos/agendamento_form.html"
    form_class = AgendamentoForm
    model = Agendamento

    def get_queryset(self):
        return Agendamento.objects.filter(tenant=self.get_tenant())

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["tenant"] = self.get_tenant()
        return kw

    def form_valid(self, form):
        ag = form.save(commit=False)
        ag.save()
        messages.success(self.request, f"Agendamento #{ag.id} atualizado.")
        return redirect("agendamentos:agendamento-detail", pk=ag.id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["basic_fields"] = ["cliente", "profissional", "origem"]
        ctx["time_fields"] = ["slot", "data_inicio", "data_fim"]
        ctx["REQUIRE_SERVICO"] = getattr(settings, "REQUIRE_SERVICO", False)
        ctx["agendamento"] = self.object
        return ctx


def agendamento_action_view(request, pk, acao):  # pragma: no cover - UI somente
    ag = get_object_or_404(Agendamento, pk=pk, tenant=getattr(request.user, "tenant", None))
    try:
        if acao == "checkin":
            AgendamentoService.checkin(ag, user=request.user)
            messages.success(request, "Check-in realizado.")
        elif acao == "concluir":
            AgendamentoService.concluir(ag, user=request.user)
            messages.success(request, "Agendamento concluído.")
        elif acao == "cancelar":
            motivo = request.POST.get("motivo", "UI")
            AgendamentoService.cancelar(ag, motivo=motivo, user=request.user)
            messages.warning(request, "Agendamento cancelado.")
        elif acao == "resolver_pendencias":
            AgendamentoService.resolver_pendencias(ag, user=request.user)
            messages.success(request, "Pendências resolvidas.")
        else:
            messages.error(request, "Ação inválida")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("agendamentos:agendamento-detail", pk=ag.id)


class SlotListView(TenantMixin, generic.ListView):
    template_name = "agendamentos/slot_list.html"
    model = Slot
    paginate_by = 100

    def get_queryset(self):
        qs = Slot.objects.filter(tenant=self.get_tenant()).select_related("profissional").order_by("horario")
        data = self.request.GET.get("data")
        if data:
            qs = qs.filter(horario__date=data)
        profissional = self.request.GET.get("profissional")
        if profissional:
            qs = qs.filter(profissional_id=profissional)
        qs = qs.annotate(
            agendamentos_confirmados=Count(
                "agendamentos", filter=Q(agendamentos__status__in=["PENDENTE", "CONFIRMADO", "EM_ANDAMENTO"])
            )
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Profissionais distintos em slots (futuro)
        ctx["profissionais"] = (
            Slot.objects.filter(tenant=self.get_tenant())
            .values_list("profissional_id", "profissional__first_name", "profissional__last_name")
            .distinct()
        )
        # Lista de serviços clínicos (substitui procedimentos)
        try:
            from servicos.models import Servico

            ctx["servicos"] = Servico.objects.filter(tenant=self.get_tenant(), ativo=True, is_clinical=True).order_by(
                "nome"
            )[:500]
        except Exception:
            ctx["servicos"] = []
        slots_qs = self.get_queryset()
        total = slots_qs.count()
        # Iteração única
        utilizados = 0
        capacidade = 0
        for s in slots_qs:
            cap_tot = s.capacidade_total or 0
            cap_util = s.capacidade_utilizada or 0
            capacidade += cap_tot
            utilizados += min(cap_util, cap_tot) if cap_tot else cap_util
        ocup_pct = round((utilizados / capacidade * 100), 1) if capacidade else 0
        ctx["statistics"] = [
            {"label": "Slots", "value": total, "icon": "fas fa-clock", "color": "primary"},
            {"label": "Capacidade", "value": capacidade, "icon": "fas fa-layer-group", "color": "info"},
            {"label": "Utilizados", "value": utilizados, "icon": "fas fa-check", "color": "success"},
            {"label": "Ocupação %", "value": ocup_pct, "icon": "fas fa-percentage", "color": "warning"},
        ]
        ctx["dashboard_url"] = reverse("agendamentos:dashboard")
        return ctx


class SlotDetailView(TenantMixin, generic.DetailView):
    template_name = "agendamentos/slot_detail.html"
    model = Slot

    def get_queryset(self):
        return Slot.objects.filter(tenant=self.get_tenant()).select_related("profissional")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slot = self.object
        ctx["agendamentos"] = slot.agendamentos.select_related("cliente").all()
        ctx["waitlist"] = slot.waitlist.select_related("cliente").order_by("prioridade", "created_at")
        # clientes para inscrição (simplificado: os que não possuem agendamento neste slot)
        from clientes.models import Cliente

        ag_clientes = slot.agendamentos.values_list("cliente_id", flat=True)
        ctx["clientes"] = Cliente.objects.filter(tenant=slot.tenant).exclude(id__in=ag_clientes)[:100]
        return ctx


def gerar_slots_view(request):  # pragma: no cover - UI
    if request.method == "POST":
        from .models import Disponibilidade

        disp_id = request.POST.get("disponibilidade_id")
        if disp_id:  # suporte a geração baseada em disponibilidade existente
            disp = get_object_or_404(Disponibilidade, pk=disp_id, tenant=getattr(request.user, "tenant", None))
            created, existentes = SlotService.gerar_slots(disp)
            messages.success(request, f"{created} slots criados, {existentes} já existiam.")
        else:
            # geração ad-hoc (cria Disponibilidade transitória)
            profissional_id = request.POST.get("profissional_id")
            data = request.POST.get("data")
            hora_inicio = request.POST.get("hora_inicio")
            hora_fim = request.POST.get("hora_fim")
            duracao = int(request.POST.get("duracao_minutos", 30))
            from core.models import CustomUser

            from .models import Disponibilidade

            prof = get_object_or_404(CustomUser, pk=profissional_id)
            disp = Disponibilidade.objects.create(
                tenant=getattr(request.user, "tenant", None),
                profissional=prof,
                data=data,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                duracao_slot_minutos=duracao,
                capacidade_por_slot=1,
            )
            created, existentes = SlotService.gerar_slots(disp)
            messages.success(request, f"{created} slots gerados.")
        return redirect("agendamentos:slot-list")
    return redirect("agendamentos:slot-list")


def waitlist_inscrever_view(request, slot_id):  # pragma: no cover - UI
    from .models import WaitlistEntry

    slot = get_object_or_404(Slot, pk=slot_id, tenant=getattr(request.user, "tenant", None))
    if request.method == "POST":
        cliente_id = request.POST.get("cliente_id")
        if cliente_id:
            from clientes.models import Cliente

            cliente = get_object_or_404(Cliente, pk=cliente_id)
            try:
                WaitlistEntry.objects.get_or_create(
                    tenant=slot.tenant, slot=slot, cliente=cliente, defaults={"prioridade": 100, "status": "ATIVO"}
                )
                messages.success(request, "Cliente adicionado à lista de espera.")
            except Exception as e:
                messages.error(request, str(e))
    return redirect("agendamentos:slot-detail", pk=slot.id)


def dashboard_view(request):  # pragma: no cover - UI
    return render(request, "agendamentos/dashboard.html")


# -------------------- Disponibilidades --------------------
class DisponibilidadeListView(TenantMixin, generic.ListView):
    template_name = "agendamentos/disponibilidade_list.html"
    model = Disponibilidade
    paginate_by = 50

    def get_queryset(self):
        qs = (
            Disponibilidade.objects.filter(tenant=self.get_tenant())
            .select_related("profissional")
            .order_by("-data", "hora_inicio")
        )
        data = self.request.GET.get("data")
        if data:
            qs = qs.filter(data=data)
        profissional = self.request.GET.get("profissional")
        if profissional:
            qs = qs.filter(profissional_id=profissional)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profissionais"] = (
            Disponibilidade.objects.filter(tenant=self.get_tenant())
            .values_list("profissional_id", "profissional__first_name", "profissional__last_name")
            .distinct()
        )
        dispon_qs = self.get_queryset()
        total = dispon_qs.count()
        ativos = dispon_qs.filter(ativo=True).count()
        cap_total = 0
        for d in dispon_qs:
            cap_total += d.capacidade_por_slot or 0
        ctx["statistics"] = [
            {"label": "Janelas", "value": total, "icon": "fas fa-calendar", "color": "primary"},
            {"label": "Ativas", "value": ativos, "icon": "fas fa-toggle-on", "color": "success"},
            {
                "label": "Cap/Slot média",
                "value": round((cap_total / total), 1) if total else 0,
                "icon": "fas fa-equals",
                "color": "info",
            },
            {"label": "Inativas", "value": total - ativos, "icon": "fas fa-toggle-off", "color": "secondary"},
        ]
        ctx["dashboard_url"] = reverse("agendamentos:dashboard")
        return ctx


class DisponibilidadeDetailView(TenantMixin, generic.DetailView):
    template_name = "agendamentos/disponibilidade_detail.html"
    model = Disponibilidade

    def get_queryset(self):
        return Disponibilidade.objects.filter(tenant=self.get_tenant()).select_related("profissional")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slots"] = self.object.slots.all().order_by("horario")
        return ctx


class DisponibilidadeCreateView(TenantMixin, generic.CreateView):
    template_name = "agendamentos/disponibilidade_form.html"
    form_class = DisponibilidadeForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["tenant"] = self.get_tenant()
        return kw

    def form_valid(self, form):
        disp = form.save(commit=False)
        disp.tenant = self.get_tenant()
        disp.save()
        messages.success(self.request, "Disponibilidade criada.")
        # gerar slots automaticamente
        SlotService.gerar_slots(disp)
        return redirect("agendamentos:disponibilidade-detail", pk=disp.id)


class DisponibilidadeUpdateView(TenantMixin, generic.UpdateView):
    template_name = "agendamentos/disponibilidade_form.html"
    form_class = DisponibilidadeForm
    model = Disponibilidade

    def get_queryset(self):
        return Disponibilidade.objects.filter(tenant=self.get_tenant())

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["tenant"] = self.get_tenant()
        return kw

    def form_valid(self, form):
        disp = form.save()
        messages.success(self.request, "Disponibilidade atualizada.")
        return redirect("agendamentos:disponibilidade-detail", pk=disp.id)


# -------------------- Auditoria --------------------
class AuditoriaListView(TenantMixin, generic.ListView):
    template_name = "agendamentos/auditoria_list.html"
    model = AuditoriaAgendamento
    paginate_by = 50

    def get_queryset(self):
        qs = (
            AuditoriaAgendamento.objects.select_related("agendamento", "user")
            .filter(agendamento__tenant=self.get_tenant())
            .order_by("-created_at")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(para_status=status)
        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo_evento=tipo)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = STATUS_AGENDAMENTO
        ctx["tipos"] = AuditoriaAgendamento.objects.values_list("tipo_evento", flat=True).distinct()
        auds = self.get_queryset()
        total = auds.count()
        ctx["statistics"] = [
            {"label": "Eventos", "value": total, "icon": "fas fa-history", "color": "primary"},
            {
                "label": "Criações",
                "value": auds.filter(tipo_evento__icontains="CRIAC").count(),
                "icon": "fas fa-plus",
                "color": "success",
            },
            {
                "label": "Cancelamentos",
                "value": auds.filter(tipo_evento__icontains="CANCEL").count(),
                "icon": "fas fa-ban",
                "color": "danger",
            },
            {
                "label": "Mudanças Estado",
                "value": auds.exclude(de_status=None, para_status=None).count(),
                "icon": "fas fa-exchange-alt",
                "color": "info",
            },
        ]
        ctx["dashboard_url"] = reverse("agendamentos:dashboard")
        return ctx


# -------------------- Reagendamento --------------------
def reagendar_view(request, pk):  # pragma: no cover - UI
    ag = get_object_or_404(Agendamento, pk=pk, tenant=getattr(request.user, "tenant", None))
    if request.method == "POST":
        form = ReagendarForm(request.POST, tenant=getattr(request.user, "tenant", None))
        if form.is_valid():
            try:
                novo = AgendamentoService.reagendar(
                    agendamento=ag,
                    novo_slot=form.cleaned_data.get("novo_slot"),
                    nova_data_inicio=form.cleaned_data.get("nova_data_inicio"),
                    nova_data_fim=form.cleaned_data.get("nova_data_fim"),
                    user=request.user,
                    motivo=form.cleaned_data.get("motivo"),
                )
                messages.success(request, f"Agendamento reagendado para #{novo.id}.")
                return redirect("agendamentos:agendamento-detail", pk=novo.id)
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ReagendarForm(tenant=getattr(request.user, "tenant", None))
    return render(request, "agendamentos/reagendar_form.html", {"form": form, "agendamento": ag})


# -------------------- Waitlist Global --------------------
class WaitlistListView(TenantMixin, generic.ListView):
    template_name = "agendamentos/waitlist_list.html"
    model = WaitlistEntry
    paginate_by = 100

    def get_queryset(self):
        qs = (
            WaitlistEntry.objects.select_related("slot", "cliente", "slot__profissional")
            .filter(tenant=self.get_tenant(), status="ATIVO")
            .order_by("prioridade", "created_at")
        )
        prof = self.request.GET.get("profissional")
        if prof:
            qs = qs.filter(slot__profissional_id=prof)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profissionais"] = (
            Slot.objects.filter(tenant=self.get_tenant())
            .values_list("profissional_id", "profissional__first_name", "profissional__last_name")
            .distinct()
        )
        wl_qs = self.get_queryset()
        total = wl_qs.count()
        top3 = list(wl_qs[:3])
        ctx["statistics"] = [
            {"label": "Entradas", "value": total, "icon": "fas fa-users", "color": "primary"},
            {
                "label": "Top 1 Espera",
                "value": top3[0].cliente.__str__() if total > 0 else "-",
                "icon": "fas fa-user-clock",
                "color": "info",
            },
            {
                "label": "Top 2",
                "value": top3[1].cliente.__str__() if total > 1 else "-",
                "icon": "fas fa-user-clock",
                "color": "secondary",
            },
            {
                "label": "Top 3",
                "value": top3[2].cliente.__str__() if total > 2 else "-",
                "icon": "fas fa-user-clock",
                "color": "secondary",
            },
        ]
        ctx["dashboard_url"] = reverse("agendamentos:dashboard")
        return ctx

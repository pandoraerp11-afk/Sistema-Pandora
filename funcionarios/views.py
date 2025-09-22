# funcionarios/views.py

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import PageTitleMixin, TenantRequiredMixin
from core.utils import get_current_tenant
from shared.mixins.ui_permissions import UIPermissionsMixin
from shared.services.ui_permissions import build_ui_permissions

from .forms import (
    BeneficioForm,
    CartaoPontoForm,
    DecimoTerceiroForm,
    DependenteFormSet,
    FeriasForm,
    FolgaForm,
    FuncionarioForm,
    HorarioTrabalhoFormSet,
    RemuneracaoRegraForm,
)
from .models import (
    Beneficio,
    CartaoPonto,
    DecimoTerceiro,
    Ferias,
    Folga,
    Funcionario,
    FuncionarioRemuneracaoRegra,
)


@login_required
def funcionarios_home(request):
    """
    View para o dashboard de funcionários, mostrando estatísticas e dados relevantes.
    """
    template_name = "funcionarios/funcionarios_home.html"
    tenant = get_current_tenant(request)

    # Se não houver tenant, apenas usuários não superusuários precisam selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Queryset conforme contexto: por tenant ou agregado para superusuário sem tenant
    funcionarios_qs = Funcionario.objects.filter(tenant=tenant) if tenant else Funcionario.objects.all()

    # Estatísticas
    total_funcionarios = funcionarios_qs.count()
    ativos = funcionarios_qs.filter(data_demissao__isnull=True).count()
    inativos = funcionarios_qs.filter(data_demissao__isnull=False).count()

    # Novos funcionários (últimos 30 dias)
    data_limite = datetime.now() - timedelta(days=30)
    novos_funcionarios_qs = funcionarios_qs.filter(data_admissao__gte=data_limite)

    # Aniversariantes do mês
    mes_atual = datetime.now().month
    aniversariantes = funcionarios_qs.filter(data_nascimento__month=mes_atual, ativo=True).order_by(
        "data_nascimento__day"
    )

    # Top 5 Departamentos
    top_departamentos = (
        funcionarios_qs.filter(departamento__isnull=False)
        .values("departamento__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # ============================================================================
    # INTEGRAÇÃO COM CONTROLE DE MATERIAIS
    # ============================================================================
    materiais_stats = {}
    try:
        from .models_estoque import ResponsabilidadeMaterial, SolicitacaoMaterial
        from .services.estoque_service import EstoqueFuncionarioService

        if tenant:
            # Estatísticas de solicitações
            solicitacoes_qs = SolicitacaoMaterial.objects.filter(tenant=tenant)
            materiais_stats.update(
                {
                    "solicitacoes_pendentes": solicitacoes_qs.filter(status="PENDENTE").count(),
                    "solicitacoes_aprovadas": solicitacoes_qs.filter(status="APROVADA").count(),
                    "solicitacoes_entregues": solicitacoes_qs.filter(status="ENTREGUE").count(),
                }
            )

            # Responsabilidades ativas
            # ResponsabilidadeMaterial não possui campo tenant direto; filtra via funcionario__tenant
            responsabilidades_ativas = ResponsabilidadeMaterial.objects.filter(
                funcionario__tenant=tenant, status="ATIVO"
            ).count()
            materiais_stats["responsabilidades_ativas"] = responsabilidades_ativas

    except ImportError:
        # Módulo de estoque ainda não configurado
        pass

    ui_perms = build_ui_permissions(request.user, tenant, module_key="FUNCIONARIO")

    context = {
        "page_title": _("Dashboard de Funcionários"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_funcionarios": total_funcionarios,
        "funcionarios_ativos": ativos,
        "funcionarios_inativos": inativos,
        "novos_funcionarios_count": novos_funcionarios_qs.count(),
        "funcionarios_recentes": novos_funcionarios_qs.order_by("-data_admissao")[:5],
        "aniversariantes_mes": aniversariantes,
        "top_departamentos": top_departamentos,
        "materiais_stats": materiais_stats,  # NOVO
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


class FuncionarioMixin(TenantRequiredMixin):
    """Mixin base para views de funcionários"""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)

    def form_valid(self, form):
        if hasattr(form.instance, "tenant"):
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)


# ===================== VIEWS DE FUNCIONÁRIOS =====================


class FuncionarioListView(UIPermissionsMixin, FuncionarioMixin, PageTitleMixin, ListView):
    model = Funcionario
    template_name = "funcionarios/funcionario_list.html"
    context_object_name = "funcionarios"
    paginate_by = 20
    page_title = "Funcionários"
    app_label = "funcionarios"
    model_name = "funcionario"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("departamento", "user")
        # Filtros
        search = self.request.GET.get("search")
        departamento = self.request.GET.get("departamento")
        ativo = self.request.GET.get("ativo")  # usa ainda o parâmetro mas deriva de data_demissao

        if search:
            queryset = (
                queryset.filter(nome_completo__icontains=search)
                | queryset.filter(cpf__icontains=search)
                | queryset.filter(cargo__icontains=search)
            )

        if departamento:
            queryset = queryset.filter(departamento_id=departamento)

        if ativo == "true":
            queryset = queryset.filter(data_demissao__isnull=True)
        elif ativo == "false":
            queryset = queryset.filter(data_demissao__isnull=False)

        return queryset.order_by("nome_completo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import Department

        context["departamentos"] = Department.objects.filter(tenant=self.request.tenant)
        context["search"] = self.request.GET.get("search", "")
        context["departamento_selected"] = self.request.GET.get("departamento", "")
        context["ativo_selected"] = self.request.GET.get("ativo", "")
        context["per_page_options"] = [10, 20, 50, 100]

        # Variáveis para templates ultra-modernos
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["active_count"] = queryset.filter(data_demissao__isnull=True).count()
        context["inactive_count"] = queryset.filter(data_demissao__isnull=False).count()

        # Estatísticas recentes (últimos 30 dias)
        from datetime import datetime, timedelta

        thirty_days_ago = datetime.now() - timedelta(days=30)
        context["recent_count"] = queryset.filter(data_admissao__gte=thirty_days_ago).count()

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Funcionários", "url": None, "active": True},
        ]

        return context


class FuncionarioDetailView(UIPermissionsMixin, FuncionarioMixin, PageTitleMixin, DetailView):
    model = Funcionario
    template_name = "funcionarios/funcionario_detail.html"
    context_object_name = "funcionario"
    app_label = "funcionarios"
    model_name = "funcionario"

    def get_page_title(self):
        return f"Funcionário: {self.object.nome_completo}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario = self.object
        context.update(
            {
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Funcionários", "url": reverse("funcionarios:funcionario_list")},
                    {"title": funcionario.nome_completo, "url": None, "active": True},
                ],
                "ultimas_ferias": funcionario.ferias.order_by("-data_inicio")[:5],
                "ultimo_decimo_terceiro": funcionario.decimo_terceiro.order_by("-ano_referencia").first(),
                "folgas_recentes": funcionario.folgas.order_by("-data_inicio")[:5],
                "beneficios_ativos": funcionario.beneficios.filter(ativo=True).order_by("-data_referencia")[:10],
                "historico_salarial": funcionario.historico_salarios.order_by("-data_vigencia")[:5],
                "regras_remuneracao": funcionario.regras_remuneracao.filter(ativo=True).order_by("tipo_regra"),
                "dependentes": funcionario.dependentes.all(),
                "horarios_trabalho": funcionario.horarios.filter(ativo=True).order_by("dia_semana", "ordem"),
            }
        )
        return context


# As views originais de criação/edição foram removidas em favor do wizard multi-etapas
# e da view completa. Mantemos apenas a FuncionarioCompleteView para edições avançadas.


class FuncionarioDeleteView(UIPermissionsMixin, FuncionarioMixin, PageTitleMixin, DeleteView):
    model = Funcionario
    template_name = "funcionarios/funcionario_confirm_delete.html"
    success_url = reverse_lazy("funcionarios:funcionario_list")
    app_label = "funcionarios"
    model_name = "funcionario"

    def get_page_title(self):
        return f"Excluir: {self.object.nome_completo}"

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Funcionário excluído com sucesso!"))
        return super().delete(request, *args, **kwargs)


@login_required
@require_POST
def funcionario_desligar(request, pk):
    tenant = get_current_tenant(request)
    funcionario = get_object_or_404(Funcionario, pk=pk, tenant=tenant)
    data = request.POST.get("data_demissao")
    motivo = request.POST.get("motivo_demissao")
    if not data:
        messages.error(request, _("Informe a data de desligamento."))
        return redirect("funcionarios:funcionario_detail", pk=pk)
    try:
        data_dt = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, _("Data inválida."))
        return redirect("funcionarios:funcionario_detail", pk=pk)
    if data_dt <= funcionario.data_admissao:
        messages.error(request, _("Data de desligamento deve ser posterior à admissão."))
        return redirect("funcionarios:funcionario_detail", pk=pk)
    funcionario.data_demissao = data_dt
    funcionario.motivo_demissao = motivo
    funcionario.save()
    messages.success(request, _("Funcionário desligado com sucesso."))
    return redirect("funcionarios:funcionario_detail", pk=pk)


@login_required
@require_POST
def funcionario_reativar(request, pk):
    tenant = get_current_tenant(request)
    funcionario = get_object_or_404(Funcionario, pk=pk, tenant=tenant)
    funcionario.data_demissao = None
    funcionario.motivo_demissao = None
    funcionario.save()
    messages.success(request, _("Funcionário reativado."))
    return redirect("funcionarios:funcionario_detail", pk=pk)


class RemuneracaoRegraCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = FuncionarioRemuneracaoRegra
    form_class = RemuneracaoRegraForm
    template_name = "funcionarios/remuneracao_regra_form.html"
    page_title = "Nova Regra de Remuneração"

    def get_initial(self):
        initial = super().get_initial()
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            initial["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        funcionario_id = self.kwargs.get("funcionario_pk")
        funcionario = None
        if funcionario_id:
            funcionario = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        kwargs["tenant"] = self.request.tenant
        kwargs["funcionario"] = funcionario
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        messages.success(self.request, _("Regra de remuneração criada."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("funcionarios:funcionario_detail", kwargs={"pk": self.object.funcionario_id})


class RemuneracaoRegraDeleteView(FuncionarioMixin, PageTitleMixin, DeleteView):
    model = FuncionarioRemuneracaoRegra
    template_name = "funcionarios/remuneracao_regra_confirm_delete.html"
    page_title = "Excluir Regra de Remuneração"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, _("Regra removida."))
        success_url = self.get_success_url()
        self.object.delete()
        return redirect(success_url)

    def get_success_url(self):
        return reverse("funcionarios:funcionario_detail", kwargs={"pk": self.object.funcionario_id})


# ===================== VIEWS DE FÉRIAS =====================


class FeriasListView(FuncionarioMixin, PageTitleMixin, ListView):
    model = Ferias
    template_name = "funcionarios/ferias_list.html"
    context_object_name = "ferias_list"
    paginate_by = 20
    page_title = "Férias"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario")

        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-data_inicio")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            context["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        context["per_page_options"] = [10, 20, 50, 100]
        return context


class FeriasCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = Ferias
    form_class = FeriasForm
    template_name = "funcionarios/ferias_form.html"
    page_title = "Agendar Férias"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            kwargs["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        response = super().form_valid(form)
        messages.success(self.request, _("Férias agendadas com sucesso!"))
        return response

    def get_success_url(self):
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            return reverse("funcionarios:funcionario_ferias", kwargs={"funcionario_pk": funcionario_id})
        return reverse("funcionarios:ferias_list")


class FeriasDetailView(FuncionarioMixin, PageTitleMixin, DetailView):
    model = Ferias
    template_name = "funcionarios/ferias_detail.html"
    context_object_name = "ferias"
    page_title = "Detalhes das Férias"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["funcionario"] = self.object.funcionario
        return context


class FeriasUpdateView(FuncionarioMixin, PageTitleMixin, UpdateView):
    model = Ferias
    form_class = FeriasForm
    template_name = "funcionarios/ferias_form.html"
    page_title = "Editar Férias"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["funcionario"] = self.object.funcionario
        return context

    def get_success_url(self):
        return reverse("funcionarios:ferias_detail", kwargs={"pk": self.object.pk})


class FeriasDeleteView(FuncionarioMixin, PageTitleMixin, DeleteView):
    model = Ferias
    template_name = "funcionarios/ferias_confirm_delete.html"
    page_title = "Excluir Férias"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["funcionario"] = self.object.funcionario
        return context

    def get_success_url(self):
        funcionario_id = self.object.funcionario.pk
        return reverse("funcionarios:funcionario_ferias", kwargs={"funcionario_pk": funcionario_id})


# ===================== VIEWS DE 13º SALÁRIO =====================


class DecimoTerceiroListView(FuncionarioMixin, PageTitleMixin, ListView):
    model = DecimoTerceiro
    template_name = "funcionarios/decimo_terceiro_list.html"
    context_object_name = "decimo_terceiro_list"
    paginate_by = 20
    page_title = "13º Salário"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario")

        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        ano = self.request.GET.get("ano")
        if ano:
            queryset = queryset.filter(ano_referencia=ano)

        return queryset.order_by("-ano_referencia", "funcionario__nome_completo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            context["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        context["per_page_options"] = [10, 20, 50, 100]
        return context


class DecimoTerceiroCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = DecimoTerceiro
    form_class = DecimoTerceiroForm
    template_name = "funcionarios/decimo_terceiro_form.html"
    page_title = "Registrar 13º Salário"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            kwargs["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        response = super().form_valid(form)
        messages.success(self.request, _("13º salário registrado com sucesso!"))
        return response


# ===================== VIEWS DE FOLGAS =====================


class FolgaListView(FuncionarioMixin, PageTitleMixin, ListView):
    model = Folga
    template_name = "funcionarios/folga_list.html"
    context_object_name = "folgas"
    paginate_by = 20
    page_title = "Folgas"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario", "aprovado_por")

        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-data_inicio")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            context["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        context["per_page_options"] = [10, 20, 50, 100]
        return context


class FolgaCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = Folga
    form_class = FolgaForm
    template_name = "funcionarios/folga_form.html"
    page_title = "Solicitar Folga"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            kwargs["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        response = super().form_valid(form)
        messages.success(self.request, _("Folga solicitada com sucesso!"))
        return response


# ===================== VIEWS DE CARTÃO PONTO =====================


class CartaoPontoListView(FuncionarioMixin, PageTitleMixin, ListView):
    model = CartaoPonto
    template_name = "funcionarios/cartao_ponto_list.html"
    context_object_name = "registros_ponto"
    paginate_by = 50
    page_title = "Cartão de Ponto"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario")

        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if data_inicio:
            queryset = queryset.filter(data_hora_registro__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_hora_registro__date__lte=data_fim)

        return queryset.order_by("-data_hora_registro")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            context["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        context["per_page_options"] = [10, 20, 50, 100]
        return context


class CartaoPontoCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = CartaoPonto
    form_class = CartaoPontoForm
    template_name = "funcionarios/cartao_ponto_form.html"
    page_title = "Registrar Ponto"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            kwargs["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.ip_origem = self.get_client_ip()
        response = super().form_valid(form)
        messages.success(self.request, _("Ponto registrado com sucesso!"))
        return response

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded_for.split(",")[0] if x_forwarded_for else self.request.META.get("REMOTE_ADDR")
        return ip


# ===================== VIEWS DE BENEFÍCIOS =====================


class BeneficioListView(FuncionarioMixin, PageTitleMixin, ListView):
    model = Beneficio
    template_name = "funcionarios/beneficio_list.html"
    context_object_name = "beneficios"
    paginate_by = 20
    page_title = "Benefícios"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario")

        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        tipo = self.request.GET.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo_beneficio=tipo)

        return queryset.order_by("-data_referencia")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            context["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        context["per_page_options"] = [10, 20, 50, 100]
        return context


class BeneficioCreateView(FuncionarioMixin, PageTitleMixin, CreateView):
    model = Beneficio
    form_class = BeneficioForm
    template_name = "funcionarios/beneficio_form.html"
    page_title = "Adicionar Benefício"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        funcionario_id = self.kwargs.get("funcionario_pk")
        if funcionario_id:
            kwargs["funcionario"] = get_object_or_404(Funcionario, pk=funcionario_id, tenant=self.request.tenant)
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        response = super().form_valid(form)
        messages.success(self.request, _("Benefício adicionado com sucesso!"))
        return response


# ===================== VIEWS ESPECIAIS =====================


class FuncionarioCompleteView(FuncionarioMixin, PageTitleMixin, UpdateView):
    """View para edição completa do funcionário com dependentes e horários"""

    model = Funcionario
    form_class = FuncionarioForm
    template_name = "funcionarios/funcionario_complete_form.html"

    def get_page_title(self):
        return f"Edição Completa: {self.object.nome_completo}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["dependente_formset"] = DependenteFormSet(
                self.request.POST, instance=self.object, prefix="dependentes"
            )
            context["horario_formset"] = HorarioTrabalhoFormSet(
                self.request.POST, instance=self.object, prefix="horarios"
            )
        else:
            context["dependente_formset"] = DependenteFormSet(instance=self.object, prefix="dependentes")
            context["horario_formset"] = HorarioTrabalhoFormSet(instance=self.object, prefix="horarios")

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        dependente_formset = context["dependente_formset"]
        horario_formset = context["horario_formset"]

        with transaction.atomic():
            self.object = form.save()

            if dependente_formset.is_valid():
                dependente_formset.instance = self.object
                dependente_formset.save()

            if horario_formset.is_valid():
                horario_formset.instance = self.object
                horario_formset.save()

        messages.success(self.request, _("Funcionário atualizado com sucesso!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("funcionarios:funcionario_detail", kwargs={"pk": self.object.pk})


# ===================== VIEWS AJAX E UTILITÁRIAS =====================


def funcionario_search_ajax(request):
    """Busca AJAX para funcionários (compatível Django 5 – sem request.is_ajax)."""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return JsonResponse({"error": "Requisição inválida"}, status=400)

    term = request.GET.get("term", "")
    tenant = get_current_tenant(request)

    funcionarios = Funcionario.objects.filter(tenant=tenant, nome_completo__icontains=term, ativo=True)[:10]

    results = [{"id": f.id, "text": f.nome_completo, "cpf": f.cpf, "cargo": f.cargo} for f in funcionarios]

    return JsonResponse({"results": results})


def relatorio_ponto_funcionario(request, funcionario_pk):
    """Gera relatório de ponto de um funcionário"""
    funcionario = get_object_or_404(Funcionario, pk=funcionario_pk, tenant=request.tenant)

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    if not data_inicio or not data_fim:
        messages.error(request, _("Período deve ser informado."))
        return redirect("funcionarios:funcionario_detail", pk=funcionario_pk)

    registros = CartaoPonto.objects.filter(
        funcionario=funcionario, data_hora_registro__date__range=[data_inicio, data_fim]
    ).order_by("data_hora_registro")

    context = {
        "funcionario": funcionario,
        "registros": registros,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "page_title": f"Relatório de Ponto - {funcionario.nome_completo}",
    }

    return render(request, "funcionarios/relatorio_ponto.html", context)

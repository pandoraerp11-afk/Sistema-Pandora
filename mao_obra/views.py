# mao_obra/views.py

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import PageTitleMixin, TenantRequiredMixin
from core.utils import get_current_tenant
from shared.mixins.ui_permissions import UIPermissionsMixin

from .forms import MaoObraForm
from .models import MaoObra


@login_required
def mao_obra_home(request):
    """
    View para o dashboard de Mão de Obra, mostrando estatísticas e dados relevantes.
    """
    template_name = "mao_obra/mao_obra_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    mao_obra_qs = MaoObra.objects.filter(tenant=tenant)

    # Estatísticas
    total_registros = mao_obra_qs.count()
    total_horas = mao_obra_qs.aggregate(Sum("horas_trabalhadas"))["horas_trabalhadas__sum"] or 0
    total_valor = mao_obra_qs.aggregate(Sum("valor_hora"))["valor_hora__sum"] or 0

    # Registros recentes (últimos 30 dias)
    data_limite = datetime.now() - timedelta(days=30)
    registros_recentes = mao_obra_qs.filter(data__gte=data_limite)

    # Top 5 Funcionários por horas trabalhadas
    top_funcionarios = (
        mao_obra_qs.values("funcionario__nome_completo")
        .annotate(total_horas=Sum("horas_trabalhadas"))
        .order_by("-total_horas")[:5]
    )

    # Top 5 Obras por registros
    top_obras = mao_obra_qs.values("obra__nome").annotate(total_registros=Count("id")).order_by("-total_registros")[:5]

    context = {
        "page_title": _("Dashboard de Mão de Obra"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_registros": total_registros,
        "total_horas": total_horas,
        "total_valor": total_valor,
        "registros_recentes_count": registros_recentes.count(),
        "registros_recentes": registros_recentes.order_by("-data")[:5],
        "top_funcionarios": top_funcionarios,
        "top_obras": top_obras,
    }
    return render(request, template_name, context)


class MaoObraMixin(TenantRequiredMixin):
    """Mixin base para views de mão de obra"""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)

    def form_valid(self, form):
        if hasattr(form.instance, "tenant"):
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)


# ===================== VIEWS DE MÃO DE OBRA =====================


class MaoObraListView(UIPermissionsMixin, MaoObraMixin, PageTitleMixin, ListView):
    model = MaoObra
    template_name = "mao_obra/mao_obra_list.html"
    context_object_name = "mao_obra_list"
    paginate_by = 20
    page_title = "Mão de Obra"
    app_label = "mao_obra"
    model_name = "maoobra"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("funcionario", "obra")

        # Filtros
        search = self.request.GET.get("search")
        funcionario = self.request.GET.get("funcionario")
        obra = self.request.GET.get("obra")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if search:
            queryset = (
                queryset.filter(atividade__icontains=search)
                | queryset.filter(funcionario__nome_completo__icontains=search)
                | queryset.filter(obra__nome__icontains=search)
            )

        if funcionario:
            queryset = queryset.filter(funcionario_id=funcionario)

        if obra:
            queryset = queryset.filter(obra_id=obra)

        if data_inicio:
            queryset = queryset.filter(data__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data__lte=data_fim)

        return queryset.order_by("-data")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from funcionarios.models import Funcionario
        from obras.models import Obra

        context["funcionarios"] = Funcionario.objects.filter(tenant=self.request.tenant, ativo=True)
        context["obras"] = Obra.objects.filter(tenant=self.request.tenant, ativo=True)
        context["search"] = self.request.GET.get("search", "")
        context["funcionario_selected"] = self.request.GET.get("funcionario", "")
        context["obra_selected"] = self.request.GET.get("obra", "")
        context["data_inicio"] = self.request.GET.get("data_inicio", "")
        context["data_fim"] = self.request.GET.get("data_fim", "")
        context["per_page_options"] = [10, 20, 50, 100]

        # Variáveis para templates ultra-modernos
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["total_horas"] = queryset.aggregate(Sum("horas_trabalhadas"))["horas_trabalhadas__sum"] or 0
        context["total_valor"] = queryset.aggregate(total=Sum("horas_trabalhadas") * Sum("valor_hora"))["total"] or 0

        # Estatísticas recentes (últimos 7 dias)
        from datetime import datetime, timedelta

        seven_days_ago = datetime.now() - timedelta(days=7)
        context["recent_count"] = queryset.filter(data__gte=seven_days_ago).count()

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Mão de Obra", "url": None, "active": True},
        ]

        return context


class MaoObraDetailView(UIPermissionsMixin, MaoObraMixin, PageTitleMixin, DetailView):
    model = MaoObra
    template_name = "mao_obra/mao_obra_detail.html"
    context_object_name = "mao_obra_item"
    app_label = "mao_obra"
    model_name = "maoobra"

    def get_page_title(self):
        return f"Registro de Mão de Obra: {self.object.funcionario.nome_completo}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mao_obra = self.object

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Mão de Obra", "url": reverse("mao_obra:mao_obra_list")},
            {"title": f"{mao_obra.funcionario.nome_completo} - {mao_obra.data}", "url": None, "active": True},
        ]

        # Valor total calculado
        context["valor_total"] = mao_obra.horas_trabalhadas * mao_obra.valor_hora

        # Outros registros do mesmo funcionário na mesma obra
        tenant = get_current_tenant(self.request)
        if tenant:
            registros_relacionados = (
                MaoObra.objects.filter(tenant=tenant, funcionario=mao_obra.funcionario, obra=mao_obra.obra)
                .exclude(id=mao_obra.id)
                .order_by("-data")[:5]
            )

            # Adicionar valor total calculado para cada registro
            for registro in registros_relacionados:
                registro.valor_total_calculado = registro.horas_trabalhadas * registro.valor_hora

            context["registros_relacionados"] = registros_relacionados
        else:
            context["registros_relacionados"] = []

        return context


class MaoObraCreateView(UIPermissionsMixin, MaoObraMixin, PageTitleMixin, CreateView):
    model = MaoObra
    form_class = MaoObraForm
    template_name = "mao_obra/mao_obra_form.html"
    page_title = "Adicionar Registro de Mão de Obra"
    app_label = "mao_obra"
    model_name = "maoobra"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        response = super().form_valid(form)
        messages.success(self.request, _("Registro de mão de obra criado com sucesso!"))
        return response

    def get_success_url(self):
        return reverse("mao_obra:mao_obra_detail", kwargs={"pk": self.object.pk})


class MaoObraUpdateView(UIPermissionsMixin, MaoObraMixin, PageTitleMixin, UpdateView):
    model = MaoObra
    form_class = MaoObraForm
    template_name = "mao_obra/mao_obra_form.html"
    app_label = "mao_obra"
    model_name = "maoobra"

    def get_page_title(self):
        return f"Editar: {self.object.funcionario.nome_completo} - {self.object.data}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Registro de mão de obra atualizado com sucesso!"))
        return response

    def get_success_url(self):
        return reverse("mao_obra:mao_obra_detail", kwargs={"pk": self.object.pk})


class MaoObraDeleteView(UIPermissionsMixin, MaoObraMixin, PageTitleMixin, DeleteView):
    model = MaoObra
    template_name = "mao_obra/mao_obra_confirm_delete.html"
    success_url = reverse_lazy("mao_obra:mao_obra_list")
    app_label = "mao_obra"
    model_name = "maoobra"

    def get_page_title(self):
        return f"Excluir: {self.object.funcionario.nome_completo} - {self.object.data}"

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Registro de mão de obra excluído com sucesso!"))
        return super().delete(request, *args, **kwargs)


# ===================== VIEWS AJAX E UTILITÁRIAS =====================


def mao_obra_search_ajax(request):
    """Busca AJAX para registros de mão de obra"""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return JsonResponse({"error": "Requisição inválida"}, status=400)

    term = request.GET.get("term", "")
    tenant = get_current_tenant(request)

    registros = MaoObra.objects.filter(tenant=tenant, atividade__icontains=term).select_related("funcionario", "obra")[
        :10
    ]

    results = [
        {
            "id": r.id,
            "text": f"{r.funcionario.nome_completo} - {r.atividade}",
            "funcionario": r.funcionario.nome_completo,
            "obra": r.obra.nome,
            "data": r.data.strftime("%d/%m/%Y"),
        }
        for r in registros
    ]

    return JsonResponse({"results": results})


def relatorio_mao_obra_funcionario(request, funcionario_pk):
    """Gera relatório de mão de obra de um funcionário"""
    from funcionarios.models import Funcionario

    funcionario = get_object_or_404(Funcionario, pk=funcionario_pk, tenant=request.tenant)

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    if not data_inicio or not data_fim:
        messages.error(request, _("Período deve ser informado."))
        return redirect("funcionarios:funcionario_detail", pk=funcionario_pk)

    registros = MaoObra.objects.filter(funcionario=funcionario, data__range=[data_inicio, data_fim]).order_by("data")

    # Estatísticas
    total_horas = registros.aggregate(Sum("horas_trabalhadas"))["horas_trabalhadas__sum"] or 0
    total_valor = sum(r.horas_trabalhadas * r.valor_hora for r in registros)

    context = {
        "funcionario": funcionario,
        "registros": registros,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_horas": total_horas,
        "total_valor": total_valor,
        "page_title": f"Relatório de Mão de Obra - {funcionario.nome_completo}",
    }

    return render(request, "mao_obra/relatorio_funcionario.html", context)


def relatorio_mao_obra_obra(request, obra_pk):
    """Gera relatório de mão de obra de uma obra"""
    from obras.models import Obra

    obra = get_object_or_404(Obra, pk=obra_pk, tenant=request.tenant)

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    if not data_inicio or not data_fim:
        messages.error(request, _("Período deve ser informado."))
        return redirect("obras:obra_detail", pk=obra_pk)

    registros = (
        MaoObra.objects.filter(obra=obra, data__range=[data_inicio, data_fim])
        .order_by("data")
        .select_related("funcionario")
    )

    # Estatísticas por funcionário
    funcionarios_stats = (
        registros.values("funcionario__nome_completo")
        .annotate(total_horas=Sum("horas_trabalhadas"), total_registros=Count("id"))
        .order_by("-total_horas")
    )

    # Estatísticas gerais
    total_horas = registros.aggregate(Sum("horas_trabalhadas"))["horas_trabalhadas__sum"] or 0
    total_valor = sum(r.horas_trabalhadas * r.valor_hora for r in registros)

    context = {
        "obra": obra,
        "registros": registros,
        "funcionarios_stats": funcionarios_stats,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_horas": total_horas,
        "total_valor": total_valor,
        "page_title": f"Relatório de Mão de Obra - {obra.nome}",
    }

    return render(request, "mao_obra/relatorio_obra.html", context)

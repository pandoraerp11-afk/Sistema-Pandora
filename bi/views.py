# bi/views.py

from django.contrib import messages
from django.db.models import Avg, Count, F, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import FiltroIndicadorForm, IndicadorForm
from .models import Indicador


class BiListView(ListView):
    model = Indicador
    template_name = "bi/bi_list_ultra_modern.html"
    context_object_name = "indicadores"
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtro por busca
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) | Q(descricao__icontains=search) | Q(observacoes__icontains=search)
            )

        # Filtro por tipo
        tipo = self.request.GET.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        # Filtro por período
        periodo = self.request.GET.get("periodo")
        if periodo:
            queryset = queryset.filter(periodo=periodo)

        # Filtro por status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filtro por responsável
        responsavel = self.request.GET.get("responsavel")
        if responsavel:
            queryset = queryset.filter(responsavel=responsavel)

        # Filtro por data
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if data_inicio:
            queryset = queryset.filter(data__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data__lte=data_fim)

        return queryset.order_by("-data", "nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estatísticas para o dashboard
        total_indicadores = Indicador.objects.count()
        indicadores_ativos = Indicador.objects.filter(status="ativo").count()
        indicadores_meta_atingida = Indicador.objects.filter(meta__isnull=False, valor__gte=F("meta")).count()

        context.update(
            {
                "page_title": "Business Intelligence",
                "page_subtitle": "Dashboard de Indicadores e Métricas",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "BI", "url": "bi:bi_dashboard", "active": True},
                ],
                "can_add": True,
                "can_edit": True,
                "can_delete": True,
                "add_url": "bi:bi_create",
                "search_placeholder": "Buscar indicadores...",
                "filter_form": FiltroIndicadorForm(self.request.GET),
                "current_filters": {
                    "search": self.request.GET.get("search", ""),
                    "tipo": self.request.GET.get("tipo", ""),
                    "periodo": self.request.GET.get("periodo", ""),
                    "status": self.request.GET.get("status", ""),
                    "responsavel": self.request.GET.get("responsavel", ""),
                    "data_inicio": self.request.GET.get("data_inicio", ""),
                    "data_fim": self.request.GET.get("data_fim", ""),
                },
                "total_indicadores": total_indicadores,
                "indicadores_ativos": indicadores_ativos,
                "indicadores_meta_atingida": indicadores_meta_atingida,
                "tipos_choices": Indicador.TIPO_CHOICES,
                "periodo_choices": Indicador.PERIODO_CHOICES,
                "status_choices": Indicador.STATUS_CHOICES,
            }
        )
        return context


class BiDetailView(DetailView):
    model = Indicador
    template_name = "bi/bi_detail_ultra_modern.html"
    context_object_name = "indicador"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Indicadores relacionados (mesmo tipo)
        indicadores_relacionados = Indicador.objects.filter(tipo=self.object.tipo, status="ativo").exclude(
            id=self.object.id
        )[:5]

        context.update(
            {
                "page_title": f"Indicador: {self.object.nome}",
                "page_subtitle": f"Detalhes do indicador {self.object.get_tipo_display()}",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "BI", "url": "bi:bi_dashboard"},
                    {"name": self.object.nome, "url": "", "active": True},
                ],
                "can_edit": True,
                "can_delete": True,
                "edit_url": "bi:bi_update",
                "delete_url": "bi:bi_delete",
                "list_url": "bi:bi_dashboard",
                "indicadores_relacionados": indicadores_relacionados,
            }
        )
        return context


class BiCreateView(CreateView):
    model = Indicador
    form_class = IndicadorForm
    template_name = "bi/bi_form_ultra_modern.html"
    success_url = reverse_lazy("bi:bi_dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Novo Indicador",
                "page_subtitle": "Adicionar novo indicador de BI",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "BI", "url": "bi:bi_dashboard"},
                    {"name": "Novo Indicador", "url": "", "active": True},
                ],
                "form_title": "Adicionar Indicador",
                "submit_text": "Salvar Indicador",
                "cancel_url": "bi:bi_dashboard",
            }
        )
        return context

    def form_valid(self, form):
        # Definir o usuário que criou o indicador
        form.instance.criado_por = self.request.user

        messages.success(self.request, "Indicador criado com sucesso!")
        return super().form_valid(form)


class BiUpdateView(UpdateView):
    model = Indicador
    form_class = IndicadorForm
    template_name = "bi/bi_form_ultra_modern.html"
    success_url = reverse_lazy("bi:bi_dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Editar Indicador: {self.object.nome}",
                "page_subtitle": "Editar informações do indicador",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "BI", "url": "bi:bi_dashboard"},
                    {"name": self.object.nome, "url": "bi:bi_detail", "url_args": [self.object.pk]},
                    {"name": "Editar", "url": "", "active": True},
                ],
                "form_title": "Editar Indicador",
                "submit_text": "Salvar Alterações",
                "cancel_url": "bi:bi_dashboard",
            }
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Indicador atualizado com sucesso!")
        return super().form_valid(form)


class BiDeleteView(DeleteView):
    model = Indicador
    template_name = "bi/bi_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("bi:bi_dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Excluir Indicador: {self.object.nome}",
                "page_subtitle": "Confirmação de exclusão",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "BI", "url": "bi:bi_dashboard"},
                    {"name": self.object.nome, "url": "bi:bi_detail", "url_args": [self.object.pk]},
                    {"name": "Excluir", "url": "", "active": True},
                ],
            }
        )
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Indicador excluído com sucesso!")
        return super().delete(request, *args, **kwargs)


# Views para Dashboard e Relatórios
def dashboard_view(request):
    """View principal do dashboard BI"""

    # Estatísticas gerais
    total_indicadores = Indicador.objects.count()
    indicadores_ativos = Indicador.objects.filter(status="ativo").count()

    # Indicadores por tipo
    indicadores_por_tipo = Indicador.objects.values("tipo").annotate(total=Count("id")).order_by("tipo")

    # Indicadores com metas atingidas
    indicadores_meta_atingida = Indicador.objects.filter(meta__isnull=False, valor__gte=F("meta")).count()

    # Últimos indicadores atualizados
    indicadores_recentes = Indicador.objects.filter(status="ativo").order_by("-data_atualizacao")[:5]

    # Indicadores críticos (abaixo da meta)
    indicadores_criticos = Indicador.objects.filter(meta__isnull=False, valor__lt=F("meta"), status="ativo").order_by(
        "-data"
    )[:5]

    context = {
        "page_title": "Dashboard BI",
        "page_subtitle": "Visão geral dos indicadores",
        "breadcrumb_items": [
            {"name": "Dashboard", "url": "dashboard"},
            {"name": "BI Dashboard", "url": "", "active": True},
        ],
        "total_indicadores": total_indicadores,
        "indicadores_ativos": indicadores_ativos,
        "indicadores_meta_atingida": indicadores_meta_atingida,
        "indicadores_por_tipo": indicadores_por_tipo,
        "indicadores_recentes": indicadores_recentes,
        "indicadores_criticos": indicadores_criticos,
    }

    return render(request, "bi/dashboard_ultra_modern.html", context)


# API Views para AJAX
def api_indicador_stats(request):
    """API para estatísticas de indicadores"""

    stats = {
        "total_indicadores": Indicador.objects.count(),
        "indicadores_ativos": Indicador.objects.filter(status="ativo").count(),
        "indicadores_por_tipo": list(Indicador.objects.values("tipo").annotate(total=Count("id")).order_by("tipo")),
        "media_valores": Indicador.objects.filter(status="ativo").aggregate(media=Avg("valor"))["media"] or 0,
        "indicadores_meta_atingida": Indicador.objects.filter(meta__isnull=False, valor__gte=F("meta")).count(),
    }

    return JsonResponse(stats)

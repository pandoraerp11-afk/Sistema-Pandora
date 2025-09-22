from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

# treinamento/views.py
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant

from .forms import TreinamentoForm  # CORRIGIDO para importar de .forms
from .models import Treinamento  # CORRIGIDO para importar de .models


@login_required
def treinamento_home(request):
    """
    View para o dashboard de Treinamentos, mostrando estatísticas e dados relevantes.
    """
    template_name = "treinamento/treinamento_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Treinamentos"),
        "subtitulo": _("Visão geral do módulo Treinamentos"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class TreinamentoListView(ListView):
    model = Treinamento  # Já estava correto
    template_name = "treinamento/treinamento_list_ultra_modern.html"
    context_object_name = "treinamento_list"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Variáveis para templates ultra-modernos
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["active_count"] = (
            queryset.filter(ativo=True).count() if hasattr(Treinamento, "ativo") else queryset.count()
        )
        context["inactive_count"] = queryset.filter(ativo=False).count() if hasattr(Treinamento, "ativo") else 0

        # Estatísticas recentes (últimos 30 dias)
        from datetime import datetime, timedelta

        thirty_days_ago = datetime.now() - timedelta(days=30)
        context["recent_count"] = (
            queryset.filter(data_criacao__gte=thirty_days_ago).count() if hasattr(Treinamento, "data_criacao") else 0
        )

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Treinamentos", "url": None, "active": True},
        ]

        return context


class TreinamentoDetailView(DetailView):
    model = Treinamento  # Já estava correto
    template_name = "treinamento/treinamento_detail_ultra_modern.html"
    context_object_name = "treinamento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Treinamentos", "url": reverse("treinamento:treinamento_list")},
            {
                "title": self.object.titulo if hasattr(self.object, "titulo") else f"Treinamento #{self.object.id}",
                "url": None,
                "active": True,
            },
        ]

        return context


class TreinamentoCreateView(CreateView):
    model = Treinamento  # Já estava correto
    form_class = TreinamentoForm  # Já estava correto
    template_name = "treinamento/treinamento_form_ultra_modern.html"
    success_url = reverse_lazy("treinamento:treinamento_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Adicionar Treinamento"

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Treinamentos", "url": reverse("treinamento:treinamento_list")},
            {"title": "Novo Treinamento", "url": None, "active": True},
        ]

        return context


class TreinamentoUpdateView(UpdateView):
    model = Treinamento  # Já estava correto
    form_class = TreinamentoForm  # Já estava correto
    template_name = "treinamento/treinamento_form_ultra_modern.html"
    success_url = reverse_lazy("treinamento:treinamento_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar Treinamento"

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Treinamentos", "url": reverse("treinamento:treinamento_list")},
            {
                "title": self.object.titulo if hasattr(self.object, "titulo") else f"Treinamento #{self.object.id}",
                "url": reverse("treinamento:treinamento_detail", kwargs={"pk": self.object.pk}),
            },
            {"title": "Editar", "url": None, "active": True},
        ]

        return context


class TreinamentoDeleteView(DeleteView):
    model = Treinamento  # Já estava correto
    template_name = "treinamento/treinamento_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("treinamento:treinamento_list")

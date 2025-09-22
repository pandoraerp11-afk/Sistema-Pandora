from django.contrib import messages
from django.contrib.auth.decorators import login_required

# orcamentos/views.py
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import OrcamentoForm  # CORRIGIDO para importar OrcamentoForm (singular)
from .models import Orcamento  # CORRIGIDO para importar Orcamento (singular)


@login_required
def orcamentos_home(request):
    """Dashboard de Orçamentos com gating UI."""
    template_name = "orcamentos/orcamentos_home.html"
    tenant = get_current_tenant(request)

    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    ui_perms = (
        build_ui_permissions(request.user, tenant, app_label="orcamentos", model_name="orcamento")
        if tenant
        else {"can_view": True, "can_add": True, "can_edit": True, "can_delete": True}
    )

    context = {
        "titulo": _("Orçamentos"),
        "subtitulo": _("Visão geral do módulo Orçamentos"),
        "tenant": tenant,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


class OrcamentosListView(ListView):  # O nome da classe da View pode ser plural
    model = Orcamento  # CORRIGIDO para Orcamento (singular)
    template_name = "orcamentos/orcamentos_list_ultra_modern.html"
    context_object_name = "orcamentos_list"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Variáveis para templates ultra-modernos
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["active_count"] = (
            queryset.filter(ativo=True).count() if hasattr(Orcamento, "ativo") else queryset.count()
        )
        context["inactive_count"] = queryset.filter(ativo=False).count() if hasattr(Orcamento, "ativo") else 0

        # Estatísticas recentes (últimos 30 dias)
        from datetime import datetime, timedelta

        thirty_days_ago = datetime.now() - timedelta(days=30)
        context["recent_count"] = (
            queryset.filter(data_criacao__gte=thirty_days_ago).count() if hasattr(Orcamento, "data_criacao") else 0
        )

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse_lazy("dashboard")},
            {"title": "Orçamentos", "url": None, "active": True},
        ]

        return context


class OrcamentosDetailView(DetailView):
    model = Orcamento  # CORRIGIDO para Orcamento (singular)
    template_name = "orcamentos/orcamentos_detail_ultra_modern.html"
    context_object_name = "orcamento"  # Convenção: singular para o objeto de detalhe

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse_lazy("dashboard")},
            {"title": "Orçamentos", "url": reverse_lazy("orcamentos:orcamentos_list")},
            {"title": f"Orçamento #{self.object.id}", "url": None, "active": True},
        ]

        return context


class OrcamentosCreateView(CreateView):
    model = Orcamento  # CORRIGIDO para Orcamento (singular)
    form_class = OrcamentoForm  # CORRIGIDO para OrcamentoForm (singular)
    template_name = "orcamentos/orcamentos_form_ultra_modern.html"
    success_url = reverse_lazy("orcamentos:orcamentos_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Adicionar Orçamento"  # Singular

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse_lazy("dashboard")},
            {"title": "Orçamentos", "url": reverse_lazy("orcamentos:orcamentos_list")},
            {"title": "Novo Orçamento", "url": None, "active": True},
        ]

        return context


class OrcamentosUpdateView(UpdateView):
    model = Orcamento  # CORRIGIDO para Orcamento (singular)
    form_class = OrcamentoForm  # CORRIGIDO para OrcamentoForm (singular)
    template_name = "orcamentos/orcamentos_form_ultra_modern.html"
    success_url = reverse_lazy("orcamentos:orcamentos_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar Orçamento"  # Singular

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse_lazy("dashboard")},
            {"title": "Orçamentos", "url": reverse_lazy("orcamentos:orcamentos_list")},
            {
                "title": f"Orçamento #{self.object.id}",
                "url": reverse_lazy("orcamentos:orcamentos_detail", kwargs={"pk": self.object.pk}),
            },
            {"title": "Editar", "url": None, "active": True},
        ]

        return context


class OrcamentosDeleteView(DeleteView):
    model = Orcamento  # CORRIGIDO para Orcamento (singular)
    template_name = "orcamentos/orcamentos_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("orcamentos:orcamentos_list")

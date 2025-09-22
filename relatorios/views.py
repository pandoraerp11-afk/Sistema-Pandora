from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

# relatorios/views.py
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant

from .forms import RelatorioForm  # CORRIGIDO para importar RelatorioForm (singular)
from .models import Relatorio  # CORRIGIDO para importar Relatorio (singular)


@login_required
def relatorios_home(request):
    """
    View para o dashboard de Relatórios, mostrando estatísticas e dados relevantes.
    """
    template_name = "relatorios/relatorios_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Relatórios"),
        "subtitulo": _("Visão geral do módulo Relatórios"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class RelatoriosListView(ListView):  # O nome da classe da View pode ser plural
    model = Relatorio  # CORRIGIDO para Relatorio (singular)
    template_name = "relatorios/relatorios_list_ultra_modern.html"
    context_object_name = "relatorios_list"
    paginate_by = 10


class RelatoriosDetailView(DetailView):
    model = Relatorio  # CORRIGIDO para Relatorio (singular)
    template_name = "relatorios/relatorios_detail_ultra_modern.html"
    context_object_name = "relatorio"  # Convenção: singular para o objeto de detalhe


class RelatoriosCreateView(CreateView):
    model = Relatorio  # CORRIGIDO para Relatorio (singular)
    form_class = RelatorioForm  # CORRIGIDO para RelatorioForm (singular)
    template_name = "relatorios/relatorios_form_ultra_modern.html"
    success_url = reverse_lazy("relatorios:relatorios_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Adicionar Relatório"  # Singular
        return context


class RelatoriosUpdateView(UpdateView):
    model = Relatorio  # CORRIGIDO para Relatorio (singular)
    form_class = RelatorioForm  # CORRIGIDO para RelatorioForm (singular)
    template_name = "relatorios/relatorios_form_ultra_modern.html"
    success_url = reverse_lazy("relatorios:relatorios_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar Relatório"  # Singular
        return context


class RelatoriosDeleteView(DeleteView):
    model = Relatorio  # CORRIGIDO para Relatorio (singular)
    template_name = "relatorios/relatorios_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("relatorios:relatorios_list")

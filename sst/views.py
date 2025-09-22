from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

# sst/views.py
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import DocumentoSSTForm  # CORRIGIDO para importar DocumentoSSTForm (singular)
from .models import DocumentoSST  # CORRIGIDO para importar DocumentoSST (singular)


@login_required
def sst_home(request):
    """Dashboard do módulo SST com gating de permissões UI."""
    template_name = "sst/sst_home.html"
    tenant = get_current_tenant(request)

    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    ui_perms = build_ui_permissions(request.user, tenant, app_label="sst", model_name="documentosst")

    context = {
        "titulo": _("SST"),
        "subtitulo": _("Visão geral do módulo SST"),
        "tenant": tenant,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


class SstListView(ListView):
    model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
    template_name = "sst/sst_list_ultra_modern.html"
    context_object_name = "sst_list"  # Pode ser 'documentos_sst_list' para clareza
    paginate_by = 10


class SstDetailView(DetailView):
    model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
    template_name = "sst/sst_detail_ultra_modern.html"
    context_object_name = "documento_sst"  # Nome do objeto no contexto


class SstCreateView(CreateView):
    model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
    form_class = DocumentoSSTForm  # CORRIGIDO para DocumentoSSTForm (singular)
    template_name = "sst/sst_form_ultra_modern.html"
    success_url = reverse_lazy("sst:sst_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Adicionar Documento SST"  # Ajustado
        return context


class SstUpdateView(UpdateView):
    model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
    form_class = DocumentoSSTForm  # CORRIGIDO para DocumentoSSTForm (singular)
    template_name = "sst/sst_form_ultra_modern.html"
    success_url = reverse_lazy("sst:sst_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar Documento SST"  # Ajustado
        return context


class SstDeleteView(DeleteView):
    model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
    template_name = "sst/sst_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("sst:sst_list")

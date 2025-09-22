from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# apropriacao/views.py
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant

from .forms import ApropriacaoForm
from .models import Apropriacao


@login_required
def apropriacao_home(request):
    """
    View para o dashboard de Apropriação, mostrando estatísticas e dados relevantes.
    """
    template_name = "apropriacao/apropriacao_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Apropriação"),
        "subtitulo": _("Visão geral do módulo Apropriação"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class ApropriacaoListView(ListView):
    model = Apropriacao
    template_name = "apropriacao/apropriacao_list_ultra_modern.html"
    context_object_name = "apropriacao_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Apropriacao.objects.select_related("obra", "responsavel").all()

        # Filtro de busca
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(descricao__icontains=search)
                | Q(obra__nome__icontains=search)
                | Q(responsavel__nome__icontains=search)
                | Q(observacoes__icontains=search)
            )

        return queryset.order_by("-data")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = context["apropriacao_list"]  # Para compatibilidade com template ultra-moderno
        context["page_title"] = "Apropriações"
        context["page_subtitle"] = "Gestão de apropriações de obras"
        context["can_add"] = True
        context["add_url"] = "apropriacao:apropriacao_create"
        context["search_placeholder"] = "Buscar por descrição, obra, responsável..."
        return context


class ApropriacaoDetailView(DetailView):
    model = Apropriacao
    template_name = "apropriacao/apropriacao_detail_ultra_modern.html"
    context_object_name = "apropriacao"

    def get_queryset(self):
        return Apropriacao.objects.select_related("obra", "responsavel").all()


class ApropriacaoCreateView(CreateView):
    model = Apropriacao
    form_class = ApropriacaoForm
    template_name = "apropriacao/apropriacao_form_ultra_modern.html"
    success_url = reverse_lazy("apropriacao:apropriacao_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova Apropriação"
        context["page_subtitle"] = "Cadastre uma nova apropriação no sistema"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Apropriação criada com sucesso!")
        return super().form_valid(form)


class ApropriacaoUpdateView(UpdateView):
    model = Apropriacao
    form_class = ApropriacaoForm
    template_name = "apropriacao/apropriacao_form_ultra_modern.html"
    success_url = reverse_lazy("apropriacao:apropriacao_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar Apropriação"
        context["page_subtitle"] = "Atualize as informações da apropriação"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Apropriação atualizada com sucesso!")
        return super().form_valid(form)


class ApropriacaoDeleteView(DeleteView):
    model = Apropriacao
    template_name = "apropriacao/apropriacao_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("apropriacao:apropriacao_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Apropriação excluída com sucesso!")
        return super().delete(request, *args, **kwargs)

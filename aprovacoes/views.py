from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

# aprovacoes/views.py
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.utils import get_current_tenant

from .forms import AprovacaoForm
from .models import Aprovacao


@login_required
def aprovacoes_home(request):
    """
    View para o dashboard de Aprovações, mostrando estatísticas e dados relevantes.
    """
    template_name = "aprovacoes/aprovacoes_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Aprovações"),
        "subtitulo": _("Visão geral do módulo Aprovações"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class AprovacoesListView(ListView):
    model = Aprovacao
    template_name = "aprovacoes/aprovacoes_list_ultra_modern.html"
    context_object_name = "aprovacoes_list"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtro por busca
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(solicitante__username__icontains=search)
                | Q(solicitante__first_name__icontains=search)
                | Q(solicitante__last_name__icontains=search)
            )

        # Filtro por status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filtro por tipo
        tipo = self.request.GET.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo_aprovacao=tipo)

        # Filtro por prioridade
        prioridade = self.request.GET.get("prioridade")
        if prioridade:
            queryset = queryset.filter(prioridade=prioridade)

        return queryset.order_by("-data_solicitacao")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Aprovações",
                "page_subtitle": "Gerenciamento de Aprovações",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "Aprovações", "url": "aprovacoes:aprovacoes_list", "active": True},
                ],
                "can_add": True,
                "can_edit": True,
                "can_delete": True,
                "add_url": "aprovacoes:aprovacoes_create",
                "search_placeholder": "Buscar aprovações...",
                "status_choices": Aprovacao.STATUS_CHOICES,
                "tipo_choices": Aprovacao.TIPO_CHOICES,
                "prioridade_choices": Aprovacao.PRIORIDADE_CHOICES,
                "current_filters": {
                    "search": self.request.GET.get("search", ""),
                    "status": self.request.GET.get("status", ""),
                    "tipo": self.request.GET.get("tipo", ""),
                    "prioridade": self.request.GET.get("prioridade", ""),
                },
            }
        )
        return context


class AprovacoesDetailView(DetailView):
    model = Aprovacao
    template_name = "aprovacoes/aprovacoes_detail_ultra_modern.html"
    context_object_name = "aprovacao"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Aprovação #{self.object.id}",
                "page_subtitle": self.object.titulo or "Detalhes da Aprovação",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "Aprovações", "url": "aprovacoes:aprovacoes_list"},
                    {"name": f"Aprovação #{self.object.id}", "url": "", "active": True},
                ],
                "can_edit": True,
                "can_delete": True,
                "edit_url": "aprovacoes:aprovacoes_update",
                "delete_url": "aprovacoes:aprovacoes_delete",
                "list_url": "aprovacoes:aprovacoes_list",
            }
        )
        return context


class AprovacoesCreateView(CreateView):
    model = Aprovacao
    form_class = AprovacaoForm
    template_name = "aprovacoes/aprovacoes_form_ultra_modern.html"
    success_url = reverse_lazy("aprovacoes:aprovacoes_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Nova Aprovação",
                "page_subtitle": "Adicionar nova aprovação",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "Aprovações", "url": "aprovacoes:aprovacoes_list"},
                    {"name": "Nova Aprovação", "url": "", "active": True},
                ],
                "form_title": "Adicionar Aprovação",
                "submit_text": "Salvar Aprovação",
                "cancel_url": "aprovacoes:aprovacoes_list",
            }
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Aprovação criada com sucesso!")
        return super().form_valid(form)


class AprovacoesUpdateView(UpdateView):
    model = Aprovacao
    form_class = AprovacaoForm
    template_name = "aprovacoes/aprovacoes_form_ultra_modern.html"
    success_url = reverse_lazy("aprovacoes:aprovacoes_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Editar Aprovação #{self.object.id}",
                "page_subtitle": self.object.titulo or "Editar aprovação",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "Aprovações", "url": "aprovacoes:aprovacoes_list"},
                    {
                        "name": f"Aprovação #{self.object.id}",
                        "url": "aprovacoes:aprovacoes_detail",
                        "url_args": [self.object.pk],
                    },
                    {"name": "Editar", "url": "", "active": True},
                ],
                "form_title": "Editar Aprovação",
                "submit_text": "Salvar Alterações",
                "cancel_url": "aprovacoes:aprovacoes_list",
            }
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Aprovação atualizada com sucesso!")
        return super().form_valid(form)


class AprovacoesDeleteView(DeleteView):
    model = Aprovacao
    template_name = "aprovacoes/aprovacoes_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("aprovacoes:aprovacoes_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Excluir Aprovação #{self.object.id}",
                "page_subtitle": "Confirmação de exclusão",
                "breadcrumb_items": [
                    {"name": "Dashboard", "url": "dashboard"},
                    {"name": "Aprovações", "url": "aprovacoes:aprovacoes_list"},
                    {
                        "name": f"Aprovação #{self.object.id}",
                        "url": "aprovacoes:aprovacoes_detail",
                        "url_args": [self.object.pk],
                    },
                    {"name": "Excluir", "url": "", "active": True},
                ],
            }
        )
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Aprovação excluída com sucesso!")
        return super().delete(request, *args, **kwargs)


# Views para AJAX
def aprovar_aprovacao(request, pk):
    """View para aprovar uma aprovação via AJAX"""
    if request.method == "POST":
        try:
            aprovacao = get_object_or_404(Aprovacao, pk=pk)
            aprovacao.status = "aprovado"
            aprovacao.data_aprovacao = timezone.now()
            aprovacao.aprovador = request.user
            aprovacao.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Aprovação aprovada com sucesso!",
                    "new_status": aprovacao.get_status_display(),
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Erro ao aprovar: {str(e)}"})

    return JsonResponse({"success": False, "message": "Método não permitido"})


def rejeitar_aprovacao(request, pk):
    """View para rejeitar uma aprovação via AJAX"""
    if request.method == "POST":
        try:
            aprovacao = get_object_or_404(Aprovacao, pk=pk)
            aprovacao.status = "rejeitado"
            aprovacao.data_aprovacao = timezone.now()
            aprovacao.aprovador = request.user
            aprovacao.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Aprovação rejeitada com sucesso!",
                    "new_status": aprovacao.get_status_display(),
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Erro ao rejeitar: {str(e)}"})

    return JsonResponse({"success": False, "message": "Método não permitido"})

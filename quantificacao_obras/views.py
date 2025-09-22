from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import ModuleRequiredMixin, PageTitleMixin, TenantRequiredMixin
from core.utils import get_current_tenant

from .forms import AnexoQuantificacaoForm, ItemQuantificacaoForm, ProjetoQuantificacaoForm
from .models import AnexoQuantificacao, ItemQuantificacao, ProjetoQuantificacao
from .serializers import AnexoQuantificacaoSerializer, ItemQuantificacaoSerializer, ProjetoQuantificacaoSerializer

# --- API Views (Django REST Framework) ---


@login_required
def quantificacao_obras_home(request):
    """
    View para o home de Quantificação de Obras, mostrando estatísticas e dados relevantes.
    """
    template_name = "quantificacao_obras/quantificacao_obras_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Quantificação de Obras"),
        "subtitulo": _("Visão geral do módulo Quantificação de Obras"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


class ProjetoQuantificacaoViewSet(viewsets.ModelViewSet):
    # ordering explícito para evitar UnorderedObjectListWarning em paginação/offset
    queryset = ProjetoQuantificacao.objects.all().order_by("id")
    serializer_class = ProjetoQuantificacaoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return self.queryset.filter(tenant=tenant)
        return self.queryset.none()

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        if not tenant:
            raise serializers.ValidationError("Tenant não encontrado.")
        serializer.save(tenant=tenant, responsavel=self.request.user)

    @action(detail=True, methods=["post"])
    def upload_anexo(self, request, pk=None):
        projeto = self.get_object()
        serializer = AnexoQuantificacaoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(projeto=projeto, upload_por=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemQuantificacaoViewSet(viewsets.ModelViewSet):
    queryset = ItemQuantificacao.objects.all().order_by("id")
    serializer_class = ItemQuantificacaoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return self.queryset.filter(projeto__tenant=tenant)
        return self.queryset.none()


class AnexoQuantificacaoViewSet(viewsets.ModelViewSet):
    queryset = AnexoQuantificacao.objects.all().order_by("id")
    serializer_class = AnexoQuantificacaoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return self.queryset.filter(projeto__tenant=tenant)
        return self.queryset.none()


# --- Template Views (Django Views) ---


class ProjetoQuantificacaoListView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, ListView
):
    model = ProjetoQuantificacao
    template_name = "quantificacao_obras/projeto_list_ultra_modern.html"
    context_object_name = "projetos"
    page_title = "Projetos de Quantificação"
    page_subtitle = "Gerencie seus projetos de quantificação de obras"
    required_module = "quantificacao_obras"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset().filter(tenant=tenant)
        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(Q(nome__icontains=search) | Q(descricao__icontains=search))
        return queryset.order_by("-created_at")


class ProjetoQuantificacaoCreateView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, CreateView
):
    model = ProjetoQuantificacao
    form_class = ProjetoQuantificacaoForm
    template_name = "quantificacao_obras/projeto_form_ultra_modern.html"
    success_url = reverse_lazy("quantificacao_obras:projeto_list")
    page_title = "Novo Projeto de Quantificação"
    page_subtitle = "Crie um novo projeto para quantificar materiais e serviços"
    required_module = "quantificacao_obras"

    def form_valid(self, form):
        tenant = get_current_tenant(self.request)
        form.instance.tenant = tenant
        form.instance.responsavel = self.request.user
        return super().form_valid(form)


class ProjetoQuantificacaoDetailView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, DetailView
):
    model = ProjetoQuantificacao
    template_name = "quantificacao_obras/projeto_detail_ultra_modern.html"
    context_object_name = "projeto"
    page_title = "Detalhes do Projeto"
    page_subtitle = "Visualize os detalhes e itens quantificados do projeto"
    required_module = "quantificacao_obras"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(tenant=tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["itens"] = self.object.itens_quantificacao.all()
        context["anexos"] = self.object.anexos_quantificacao.all()
        context["item_form"] = ItemQuantificacaoForm()
        context["anexo_form"] = AnexoQuantificacaoForm()
        return context


class ProjetoQuantificacaoUpdateView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, UpdateView
):
    model = ProjetoQuantificacao
    form_class = ProjetoQuantificacaoForm
    template_name = "quantificacao_obras/projeto_form_ultra_modern.html"
    success_url = reverse_lazy("quantificacao_obras:projeto_list")
    page_title = "Editar Projeto de Quantificação"
    page_subtitle = "Atualize as informações do projeto"
    required_module = "quantificacao_obras"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(tenant=tenant)


class ProjetoQuantificacaoDeleteView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, DeleteView
):
    model = ProjetoQuantificacao
    template_name = "quantificacao_obras/projeto_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("quantificacao_obras:projeto_list")
    page_title = "Excluir Projeto de Quantificação"
    page_subtitle = "Confirme a exclusão deste projeto"
    required_module = "quantificacao_obras"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(tenant=tenant)


class ItemQuantificacaoCreateView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, CreateView
):
    model = ItemQuantificacao
    form_class = ItemQuantificacaoForm
    template_name = "quantificacao_obras/item_form_ultra_modern.html"
    page_title = "Adicionar Item de Quantificação"
    page_subtitle = "Adicione um novo item a este projeto"
    required_module = "quantificacao_obras"

    def get_success_url(self):
        return reverse_lazy("quantificacao_obras:projeto_detail", kwargs={"pk": self.object.projeto.pk})

    def form_valid(self, form):
        projeto_id = self.kwargs["projeto_pk"]
        projeto = get_object_or_404(ProjetoQuantificacao, pk=projeto_id, tenant=get_current_tenant(self.request))
        form.instance.projeto = projeto
        return super().form_valid(form)


class ItemQuantificacaoUpdateView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, UpdateView
):
    model = ItemQuantificacao
    form_class = ItemQuantificacaoForm
    template_name = "quantificacao_obras/item_form_ultra_modern.html"
    page_title = "Editar Item de Quantificação"
    page_subtitle = "Atualize as informações deste item"
    required_module = "quantificacao_obras"

    def get_success_url(self):
        return reverse_lazy("quantificacao_obras:projeto_detail", kwargs={"pk": self.object.projeto.pk})

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(projeto__tenant=tenant)


class ItemQuantificacaoDeleteView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, DeleteView
):
    model = ItemQuantificacao
    template_name = "quantificacao_obras/item_confirm_delete_ultra_modern.html"
    page_title = "Excluir Item de Quantificação"
    page_subtitle = "Confirme a exclusão deste item"
    required_module = "quantificacao_obras"

    def get_success_url(self):
        return reverse_lazy("quantificacao_obras:projeto_detail", kwargs={"pk": self.object.projeto.pk})

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(projeto__tenant=tenant)


class AnexoQuantificacaoCreateView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, CreateView
):
    model = AnexoQuantificacao
    form_class = AnexoQuantificacaoForm
    template_name = "quantificacao_obras/anexo_form_ultra_modern.html"
    page_title = "Adicionar Anexo"
    page_subtitle = "Faça upload de um arquivo para este projeto"
    required_module = "quantificacao_obras"

    def get_success_url(self):
        return reverse_lazy("quantificacao_obras:projeto_detail", kwargs={"pk": self.object.projeto.pk})

    def form_valid(self, form):
        projeto_id = self.kwargs["projeto_pk"]
        projeto = get_object_or_404(ProjetoQuantificacao, pk=projeto_id, tenant=get_current_tenant(self.request))
        form.instance.projeto = projeto
        form.instance.upload_por = self.request.user
        # Preencher tipo_arquivo e tamanho_arquivo automaticamente
        if form.instance.arquivo:
            form.instance.nome_arquivo = form.instance.arquivo.name
            form.instance.tipo_arquivo = (
                form.instance.arquivo.name.split(".")[-1].upper() if "." in form.instance.arquivo.name else ""
            )
            form.instance.tamanho_arquivo = form.instance.arquivo.size
        return super().form_valid(form)


class AnexoQuantificacaoDeleteView(
    LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, PageTitleMixin, DeleteView
):
    model = AnexoQuantificacao
    template_name = "quantificacao_obras/anexo_confirm_delete_ultra_modern.html"
    page_title = "Excluir Anexo"
    page_subtitle = "Confirme a exclusão deste anexo"
    required_module = "quantificacao_obras"

    def get_success_url(self):
        return reverse_lazy("quantificacao_obras:projeto_detail", kwargs={"pk": self.object.projeto.pk})

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return super().get_queryset().filter(projeto__tenant=tenant)

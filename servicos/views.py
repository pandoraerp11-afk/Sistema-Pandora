import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

# servicos/views.py (VERSÃO COMPLETA E CORRIGIDA)
from django.db import transaction
from django.db.models import Avg, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

# Importa o PageTitleMixin que estava no core/views.py
from core.mixins import PageTitleMixin, TenantRequiredMixin
from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

# Importa o novo formset que criamos
from .forms import (
    AvaliacaoForm,
    CalculoPrecoForm,
    CategoriaServicoForm,
    RegraCobrancaForm,
    ServicoClinicoForm,
    ServicoDocumentoForm,
    ServicoForm,
    ServicoFornecedorFormSet,
    ServicoImagemForm,
)
from .models import Avaliacao, CategoriaServico, RegraCobranca, Servico, ServicoDocumento, ServicoImagem

# =============================================================================
# === VIEWS BASE (PARA REUTILIZAÇÃO DE CÓDIGO) ===
# =============================================================================


class ServicoDashboardView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    """
    Dashboard principal do módulo de serviços com estatísticas gerais
    """

    model = Servico
    template_name = "servicos/servicos_home.html"
    context_object_name = "servicos"
    page_title = _("Dashboard - Serviços")
    paginate_by = 5  # Mostrar apenas os 5 mais recentes

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = Servico.objects.all()
        # Só filtra por tenant se o modelo possuir o campo 'tenant'
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-id")[:5]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        # Base global (sem tenant) e aplica filtro somente se existir campo 'tenant'
        all_servicos = Servico.objects.all()
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            all_servicos = all_servicos.filter(tenant=tenant)

        # Contagens seguras (CategoriaServico/RegraCobranca não possuem tenant)
        context.update(
            {
                "total_servicos": all_servicos.count(),
                "servicos_ofertados": all_servicos.filter(tipo_servico="OFERTADO").count(),
                "servicos_recebidos": all_servicos.filter(tipo_servico="RECEBIDO").count(),
                "servicos_ativos": all_servicos.filter(ativo=True).count(),
                "servicos_inativos": all_servicos.filter(ativo=False).count(),
                "total_categorias": CategoriaServico.objects.count(),
                "total_regras_cobranca": RegraCobranca.objects.count(),
                "titulo": _("Serviços"),
                "subtitulo": _("Visão geral do módulo Serviços"),
            }
        )
        # UI permissions
        ui_perms = build_ui_permissions(self.request.user, tenant, module_key="SERVICO")
        ui_perms_categoria = build_ui_permissions(
            self.request.user, tenant, app_label="servicos", model_name="categoriaservico"
        )
        ui_perms_regra = build_ui_permissions(
            self.request.user, tenant, app_label="servicos", model_name="regracobranca"
        )
        context["ui_perms"] = ui_perms
        context["perms_ui"] = ui_perms
        context["ui_perms_categoria"] = ui_perms_categoria
        context["perms_ui_categoria"] = ui_perms_categoria
        context["ui_perms_regra"] = ui_perms_regra
        context["perms_ui_regra"] = ui_perms_regra

        context["tenant"] = tenant
        return context


# Função de dashboard mantida para compatibilidade (será depreciada)
@login_required
def servicos_home(request):
    """DEPRECIADO: Use ServicoDashboardView.as_view() no place desta função"""
    view = ServicoDashboardView.as_view()
    return view(request)


class BaseServicoListView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    model = Servico
    template_name = "servicos/servico_list.html"
    context_object_name = "servicos"
    paginate_by = 10
    tipo_servico = None
    create_url_name = None

    def get_queryset(self):
        queryset = super().get_queryset().select_related("categoria")
        has_tenant = any(f.name == "tenant" for f in Servico._meta.get_fields())
        if has_tenant:
            tenant = get_current_tenant(self.request)
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            else:
                return queryset.none()
        queryset = queryset.filter(tipo_servico=self.tipo_servico)

        busca = self.request.GET.get("busca")
        if busca:
            queryset = queryset.filter(
                Q(nome_servico__icontains=busca) | Q(descricao_curta__icontains=busca) | Q(codigo__icontains=busca)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["create_url"] = reverse_lazy(self.create_url_name)
        context["list_url_name"] = self.request.resolver_match.view_name

        # Variáveis para templates ultra-modernos
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["active_count"] = queryset.filter(ativo=True).count()
        context["inactive_count"] = queryset.filter(ativo=False).count()

        # Estatísticas recentes (últimos 30 dias)
        from datetime import datetime, timedelta

        thirty_days_ago = datetime.now() - timedelta(days=30)
        context["recent_count"] = (
            queryset.filter(data_criacao__gte=thirty_days_ago).count() if hasattr(Servico, "data_criacao") else 0
        )

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Serviços", "url": None, "active": True},
        ]

        return context


class BaseServicoCreateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, CreateView):
    model = Servico
    form_class = ServicoForm
    template_name = "servicos/servico_form.html"
    tipo_servico = None
    success_url_name = None

    def get_initial(self):
        initial = super().get_initial()
        initial["tipo_servico"] = self.tipo_servico
        tenant = get_current_tenant(self.request)
        if tenant:
            initial["tenant"] = tenant
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Se POST, reutiliza dados enviados para preservar erros/valores ao invalidar
        if self.request.method == "POST":
            context["clinico_form"] = ServicoClinicoForm(self.request.POST, prefix="clinico")
        else:
            context["clinico_form"] = ServicoClinicoForm(prefix="clinico")
        return context

    def form_valid(self, form):
        tenant = get_current_tenant(self.request)
        if tenant:
            form.instance.tenant = tenant
        is_clinical = form.cleaned_data.get("is_clinical")
        clinico_form = ServicoClinicoForm(self.request.POST, prefix="clinico") if is_clinical else None
        # Validação antecipada: se marcado clínico mas sub-form inválido, trata como erro geral
        if is_clinical and (not clinico_form.is_valid()):
            messages.error(self.request, _("Erros no perfil clínico."))
            return self.form_invalid(form)
        # Salva serviço e perfil dentro de transação para consistência
        from django.db import transaction

        with transaction.atomic():
            response = super().form_valid(form)
            if is_clinical and clinico_form:
                perfil = clinico_form.save(commit=False)
                perfil.servico = self.object
                perfil.save()
        return response

    def form_invalid(self, form):
        messages.error(self.request, _("Erro ao criar o serviço. Verifique os campos."))
        return super().form_invalid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            _('Serviço "{}" criado com sucesso! Continue a configuração abaixo.').format(self.object.nome_servico),
        )
        return reverse(self.success_url_name, kwargs={"slug": self.object.slug})


class BaseServicoUpdateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, UpdateView):
    model = Servico
    form_class = ServicoForm
    template_name = "servicos/servico_form.html"
    slug_field = "slug"
    tipo_servico = None

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset().filter(tipo_servico=self.tipo_servico)
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = _("Editar Serviço")
        context["imagem_form"] = ServicoImagemForm()
        context["documento_form"] = ServicoDocumentoForm()
        context["imagens_existentes"] = self.object.imagens_adicionais.all().order_by("ordem")
        context["documentos_existentes"] = self.object.documentos_anexos.all()
        # Form clínico: se já existir perfil, instancia; senão vazio
        if self.request.POST:
            context["clinico_form"] = ServicoClinicoForm(
                self.request.POST, instance=getattr(self.object, "perfil_clinico", None), prefix="clinico"
            )
        else:
            context["clinico_form"] = ServicoClinicoForm(
                instance=getattr(self.object, "perfil_clinico", None), prefix="clinico"
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        clinico_form = context.get("clinico_form")
        is_clinical = bool(form.cleaned_data.get("is_clinical"))
        if is_clinical and clinico_form and not clinico_form.is_valid():
            messages.error(self.request, _("Erros no perfil clínico."))
            return self.form_invalid(form)
        obj = form.save()
        if is_clinical and clinico_form:
            perfil = clinico_form.save(commit=False)
            perfil.servico = obj
            perfil.save()
            messages.success(self.request, _('Serviço "{}" e perfil clínico atualizados.').format(obj.nome_servico))
        else:
            # Desmarcou clínico: remove perfil se existir
            if not is_clinical and hasattr(obj, "perfil_clinico"):
                obj.perfil_clinico.delete()
            messages.success(self.request, _('Serviço "{}" atualizado.').format(obj.nome_servico))
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, _("Erro ao atualizar o serviço. Verifique os campos."))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(self.request.resolver_match.view_name, kwargs={"slug": self.object.slug})


# =============================================================================
# === VIEWS PARA SERVIÇOS OFERTADOS (VENDA) ===
# =============================================================================


class ServicoOfertadoListView(BaseServicoListView):
    page_title = _("Serviços Ofertados (Venda)")
    tipo_servico = "OFERTADO"
    create_url_name = "servicos:servico_ofertado_create"


class ServicoOfertadoCreateView(BaseServicoCreateView):
    page_title = _("Adicionar Novo Serviço Ofertado")
    tipo_servico = "OFERTADO"
    success_url_name = "servicos:servico_ofertado_update"


class ServicoOfertadoUpdateView(BaseServicoUpdateView):
    tipo_servico = "OFERTADO"


# =============================================================================
# === VIEWS PARA SERVIÇOS CONTRATADOS (COMPRA) ===
# =============================================================================


class ServicoRecebidoListView(BaseServicoListView):
    page_title = _("Serviços Contratados (Compra)")
    tipo_servico = "RECEBIDO"
    create_url_name = "servicos:servico_recebido_create"


class ServicoRecebidoCreateView(BaseServicoCreateView):
    page_title = _("Adicionar Novo Serviço Contratado")
    tipo_servico = "RECEBIDO"
    success_url_name = "servicos:servico_recebido_update"


class ServicoRecebidoUpdateView(BaseServicoUpdateView):
    tipo_servico = "RECEBIDO"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["fornecedores_formset"] = ServicoFornecedorFormSet(
                self.request.POST, instance=self.object, prefix="fornecedores"
            )
        else:
            context["fornecedores_formset"] = ServicoFornecedorFormSet(instance=self.object, prefix="fornecedores")
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        fornecedores_formset = context["fornecedores_formset"]
        clinico_form = context.get("clinico_form")
        is_clinical = form.cleaned_data.get("is_clinical")

        if not fornecedores_formset.is_valid():
            messages.error(self.request, _("Por favor, corrija os erros nos dados dos fornecedores."))
            return self.form_invalid(form)
        if is_clinical and clinico_form and not clinico_form.is_valid():
            messages.error(self.request, _("Erros no perfil clínico."))
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
            fornecedores_formset.instance = self.object
            fornecedores_formset.save()
            if is_clinical and clinico_form:
                perfil = clinico_form.save(commit=False)
                perfil.servico = self.object
                perfil.save()
            elif not is_clinical and hasattr(self.object, "perfil_clinico"):
                self.object.perfil_clinico.delete()
        messages.success(
            self.request,
            _('Serviço "{}" fornecedores e perfil clínico atualizados com sucesso!').format(self.object.nome_servico),
        )
        return redirect(self.get_success_url())


# =============================================================================
# === VIEWS GENÉRICAS E DE SUB-RECURSOS (COMPARTILHADAS) ===
# =============================================================================


class ServicoDetailView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DetailView):
    model = Servico
    template_name = "servicos/servico_detail.html"
    context_object_name = "servico"
    slug_field = "slug"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servico = self.object
        self.page_title = servico.nome_servico

        avaliacoes = servico.avaliacoes.filter(aprovado=True)
        context["avaliacoes"] = avaliacoes
        context["avaliacao_media"] = avaliacoes.aggregate(Avg("nota"))["nota__avg"]
        context["calculo_form"] = CalculoPrecoForm(servico=servico)
        context["avaliacao_form"] = AvaliacaoForm()

        if servico.tipo_servico == "RECEBIDO":
            context["fornecedores_servico"] = servico.servicofornecedor_set.all().select_related(
                "fornecedor", "regra_cobranca_fornecedor"
            )

        return context


class ServicoDeleteView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DeleteView):
    model = Servico
    template_name = "servicos/servico_confirm_delete.html"
    slug_field = "slug"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = _("Excluir Serviço")
        return context

    def get_success_url(self):
        if hasattr(self, "object") and self.object.tipo_servico == "OFERTADO":
            return reverse_lazy("servicos:servico_ofertado_list")
        return reverse_lazy("servicos:servico_recebido_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        nome_servico = self.object.nome_servico
        messages.success(request, _('Serviço "{}" excluído com sucesso!').format(nome_servico))
        return super().delete(request, *args, **kwargs)


# --- Views para Imagens e Documentos ---


@login_required
@require_POST
def servico_imagem_add(request, servico_slug):
    tenant = get_current_tenant(request)
    # Buscar por slug e, se houver campo tenant, restringir
    base_qs = Servico.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        base_qs = base_qs.filter(tenant=tenant)
    servico = get_object_or_404(base_qs, slug=servico_slug)
    form = ServicoImagemForm(request.POST, request.FILES)
    if form.is_valid():
        imagem = form.save(commit=False)
        imagem.servico = servico
        imagem.save()
        messages.success(request, _("Imagem adicionada com sucesso!"))
    else:
        error_msg = _("Erro ao adicionar imagem:")
        for field, errors in form.errors.items():
            for error in errors:
                error_msg += f"<br/>{form.fields[field].label if field != '__all__' else ''}: {error}"
        messages.error(request, error_msg, extra_tags="safe")
    return redirect(servico.get_update_url())


@login_required
@require_POST
def servico_imagem_delete(request, pk):
    tenant = get_current_tenant(request)
    qs_img = ServicoImagem.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        qs_img = qs_img.filter(servico__tenant=tenant)
    imagem = get_object_or_404(qs_img, pk=pk)
    servico_update_url = imagem.servico.get_update_url()
    imagem.delete()
    messages.success(request, _("Imagem excluída com sucesso!"))
    return redirect(servico_update_url)


@login_required
@require_POST
def servico_documento_add(request, servico_slug):
    tenant = get_current_tenant(request)
    base_qs = Servico.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        base_qs = base_qs.filter(tenant=tenant)
    servico = get_object_or_404(base_qs, slug=servico_slug)
    form = ServicoDocumentoForm(request.POST, request.FILES)
    if form.is_valid():
        documento = form.save(commit=False)
        documento.servico = servico
        documento.save()
        messages.success(request, _("Documento adicionado com sucesso!"))
    else:
        error_msg = _("Erro ao adicionar documento:")
        for field, errors in form.errors.items():
            for error in errors:
                error_msg += f"<br/>{form.fields[field].label if field != '__all__' else ''}: {error}"
        messages.error(request, error_msg, extra_tags="safe")
    return redirect(servico.get_update_url())


@login_required
@require_POST
def servico_documento_delete(request, pk):
    tenant = get_current_tenant(request)
    qs_doc = ServicoDocumento.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        qs_doc = qs_doc.filter(servico__tenant=tenant)
    documento = get_object_or_404(qs_doc, pk=pk)
    servico_update_url = documento.servico.get_update_url()
    documento.delete()
    messages.success(request, _("Documento excluído com sucesso!"))
    return redirect(servico_update_url)


@login_required
def servico_documento_download(request, pk):
    tenant = get_current_tenant(request)
    qs_doc = ServicoDocumento.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        qs_doc = qs_doc.filter(servico__tenant=tenant)
    documento = get_object_or_404(qs_doc, pk=pk)
    if not documento.arquivo:
        raise Http404(_("Documento sem arquivo associado."))
    try:
        return FileResponse(documento.arquivo.open("rb"), as_attachment=True, filename=documento.filename)
    except FileNotFoundError:
        raise Http404(_("Arquivo do documento não encontrado no servidor."))
    except Exception:
        messages.error(request, _("Ocorreu um erro ao processar o download do arquivo."))
        return redirect(documento.servico.get_update_url())


# =============================================================================
# === VIEWS MANTIDAS (CATEGORIA, REGRA DE COBRANÇA, AVALIAÇÃO) ===
# =============================================================================


class CategoriaServicoListView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    model = CategoriaServico
    template_name = "servicos/servico_categoria_list.html"
    context_object_name = "object_list"
    paginate_by = 15
    page_title = _("Categorias de Serviço")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            queryset = queryset.filter(tenant=tenant)
        return queryset


class CategoriaServicoCreateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, CreateView):
    model = CategoriaServico
    form_class = CategoriaServicoForm
    template_name = "servicos/servico_categoria_form.html"
    success_url = reverse_lazy("servicos:categoria_list")
    page_title = _("Adicionar Nova Categoria de Serviço")

    def form_valid(self, form):
        tenant = get_current_tenant(self.request)
        if tenant:
            form.instance.tenant = tenant
        messages.success(self.request, _('Categoria "{}" criada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Erro ao criar a categoria. Verifique os campos."))
        return super().form_invalid(form)


class CategoriaServicoUpdateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, UpdateView):
    model = CategoriaServico
    form_class = CategoriaServicoForm
    template_name = "servicos/servico_categoria_form.html"
    success_url = reverse_lazy("servicos:categoria_list")
    slug_field = "slug"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Editar Categoria de Serviço")
        self.page_subtitle = self.object.nome
        return context

    def form_valid(self, form):
        messages.success(self.request, _('Categoria "{}" atualizada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Erro ao atualizar a categoria. Verifique os campos."))
        return super().form_invalid(form)


class CategoriaServicoDeleteView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DeleteView):
    model = CategoriaServico
    template_name = "servicos/servico_confirm_delete.html"
    success_url = reverse_lazy("servicos:categoria_list")
    slug_field = "slug"

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Excluir Categoria de Serviço")
        self.page_subtitle = self.object.nome
        context["cancel_url"] = self.success_url
        return context

    def post(self, request, *args, **kwargs):
        nome_obj = self.get_object().nome
        messages.success(request, _('Categoria "{}" excluída com sucesso!').format(nome_obj))
        return super().delete(request, *args, **kwargs)


@login_required
@require_POST
def categoria_quick_create(request):
    """Cria CategoriaServico via AJAX sem sair da tela."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)

    nome = (payload.get("nome") or "").strip()
    descricao = (payload.get("descricao") or "").strip()
    ativo = bool(payload.get("ativo", True))
    if not nome:
        return JsonResponse({"success": False, "error": "Nome é obrigatório."}, status=400)

    existente = CategoriaServico.objects.filter(nome__iexact=nome).first()
    if existente:
        return JsonResponse({"success": True, "id": existente.pk, "nome": existente.nome, "duplicated": True})

    cat = CategoriaServico(nome=nome, descricao=descricao, ativo=ativo)
    tenant = get_current_tenant(request)
    if tenant and any(f.name == "tenant" for f in CategoriaServico._meta.get_fields()):
        cat.tenant = tenant
    cat.save()
    return JsonResponse({"success": True, "id": cat.pk, "nome": cat.nome})


@login_required
@require_POST
def regra_cobranca_quick_create(request):
    """Cria RegraCobranca via AJAX sem sair da tela."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)

    nome = (payload.get("nome") or "").strip()
    if not nome:
        return JsonResponse({"success": False, "error": "Nome é obrigatório."}, status=400)

    tenant = get_current_tenant(request)
    qs = RegraCobranca.objects.filter(nome__iexact=nome)
    if tenant and any(f.name == "tenant" for f in RegraCobranca._meta.get_fields()):
        qs = qs.filter(tenant=tenant)
    existente = qs.first()
    if existente:
        return JsonResponse({"success": True, "id": existente.pk, "nome": existente.nome, "duplicated": True})

    # Montar kwargs; campos numéricos podem vir como string
    def to_decimal(v, default="0"):
        if v in (None, ""):
            v = default
        try:
            return Decimal(str(v).replace(",", "."))
        except Exception:
            return Decimal(default)

    from decimal import Decimal

    kwargs = dict(
        nome=nome,
        descricao=(payload.get("descricao") or "").strip(),
        valor_base=to_decimal(payload.get("valor_base"), "0"),
        valor_minimo=to_decimal(payload.get("valor_minimo"), "0"),
        incremento=to_decimal(payload.get("incremento"), "1"),
        taxa_adicional=to_decimal(payload.get("taxa_adicional"), "0"),
        tipo_calculo=payload.get("tipo_calculo") or "unidade",
        formula_personalizada=(payload.get("formula_personalizada") or "").strip(),
        ativo=bool(payload.get("ativo", True)),
    )

    und_id = payload.get("unidade_medida")
    if und_id:
        try:
            from cadastros_gerais.models import UnidadeMedida

            kwargs["unidade_medida"] = UnidadeMedida.objects.get(pk=und_id)
        except Exception:
            return JsonResponse({"success": False, "error": "Unidade inválida."}, status=400)

    regra = RegraCobranca(**kwargs)
    if tenant and any(f.name == "tenant" for f in RegraCobranca._meta.get_fields()):
        regra.tenant = tenant
    regra.save()
    return JsonResponse({"success": True, "id": regra.pk, "nome": regra.nome})


@login_required
def unidades_medida_options(request):
    try:
        from cadastros_gerais.models import UnidadeMedida
    except Exception:
        return JsonResponse({"results": []})
    qs = UnidadeMedida.objects.all().order_by("nome")[:500]
    data = [{"id": u.pk, "text": f"{u.nome} ({u.simbolo})"} for u in qs]
    return JsonResponse({"results": data})


class RegraCobrancaListView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    model = RegraCobranca
    template_name = "servicos/regra_cobranca_list.html"
    context_object_name = "object_list"
    paginate_by = 15
    page_title = _("Regras de Cobrança")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
            queryset = queryset.filter(tenant=tenant)
        return queryset


class RegraCobrancaCreateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, CreateView):
    model = RegraCobranca
    form_class = RegraCobrancaForm
    template_name = "servicos/regra_cobranca_form.html"
    success_url = reverse_lazy("servicos:regra_cobranca_list")
    page_title = _("Adicionar Nova Regra de Cobrança")

    def form_valid(self, form):
        tenant = get_current_tenant(self.request)
        if tenant:
            form.instance.tenant = tenant
        messages.success(self.request, _('Regra de Cobrança "{}" criada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)


class RegraCobrancaUpdateView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, UpdateView):
    model = RegraCobranca
    form_class = RegraCobrancaForm
    template_name = "servicos/regra_cobranca_form.html"
    success_url = reverse_lazy("servicos:regra_cobranca_list")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Editar Regra de Cobrança")
        self.page_subtitle = self.object.nome
        return context

    def form_valid(self, form):
        messages.success(self.request, _('Regra de Cobrança "{}" atualizada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)


class RegraCobrancaDeleteView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DeleteView):
    model = RegraCobranca
    template_name = "servicos/generic_confirm_delete.html"
    success_url = reverse_lazy("servicos:regra_cobranca_list")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = super().get_queryset()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Excluir Regra de Cobrança")
        self.page_subtitle = self.object.nome
        context["cancel_url"] = self.success_url
        return context

    def post(self, request, *args, **kwargs):
        nome_obj = self.get_object().nome
        messages.success(request, _('Regra de Cobrança "{}" excluída com sucesso!').format(nome_obj))
        return super().delete(request, *args, **kwargs)


@login_required
def servico_avaliacao_add(request, servico_slug):
    tenant = get_current_tenant(request)
    base_qs = Servico.objects.all()
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        base_qs = base_qs.filter(tenant=tenant)
    servico = get_object_or_404(base_qs, slug=servico_slug)
    if request.method == "POST":
        form = AvaliacaoForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.servico = servico
            avaliacao.save()
            messages.success(request, _("Sua avaliação foi enviada e aguarda moderação. Obrigado!"))
            return redirect(servico.get_absolute_url() + "#avaliacoes")
        else:
            error_list = "<ul class='list-unstyled mb-0'>"
            for field, errors in form.errors.items():
                for error in errors:
                    error_list += f"<li>{form.fields[field].label if field != '__all__' else ''}: {error}</li>"
            error_list += "</ul>"
            messages.error(request, _("Erro ao submeter sua avaliação:") + error_list, extra_tags="safe")
            return redirect(servico.get_absolute_url() + "#avaliacoes-form-section")

    return redirect(servico.get_absolute_url())


@login_required
@require_POST
def servico_avaliacao_aprovar(request, pk):
    tenant = get_current_tenant(request)
    qs_av = Avaliacao.objects.select_related("servico")
    if tenant and any(f.name == "tenant" for f in Servico._meta.get_fields()):
        qs_av = qs_av.filter(servico__tenant=tenant)
    avaliacao = get_object_or_404(qs_av, pk=pk)
    avaliacao.aprovado = True
    avaliacao.save()
    messages.success(request, _("Avaliação aprovada com sucesso!"))
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("servicos:avaliacao_list")))


@login_required
@require_POST
def servico_avaliacao_rejeitar_ou_excluir(request, pk):
    tenant = get_current_tenant(request)
    avaliacao = get_object_or_404(Avaliacao, pk=pk, servico__tenant=tenant)
    action = request.POST.get("action", "excluir")

    if action == "rejeitar":
        avaliacao.aprovado = False
        avaliacao.save()
        messages.info(request, _('Avaliação de "{}" foi marcada como não aprovada.').format(avaliacao.nome_cliente))
    else:
        nome_cliente = avaliacao.nome_cliente
        avaliacao.delete()
        messages.success(request, _('Avaliação de "{}" foi excluída com sucesso.').format(nome_cliente))
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("servicos:avaliacao_list")))


@login_required
def calcular_preco_servico(request, servico_slug):
    tenant = get_current_tenant(request)
    servico = get_object_or_404(Servico, slug=servico_slug, tenant=tenant)
    if request.method == "POST":
        form = CalculoPrecoForm(request.POST, servico=servico)
        if form.is_valid():
            quantidade = form.cleaned_data["quantidade"]
            try:
                preco = servico.calcular_preco(quantidade)
                return JsonResponse(
                    {
                        "preco_calculado": float(preco),
                        "preco_formatado": f"R$ {preco:_.2f}".replace(".", ",").replace("_", "."),
                        "success": True,
                    }
                )
            except Exception:
                return JsonResponse({"error": _("Erro interno ao calcular o preço."), "success": False}, status=500)
        else:
            return JsonResponse({"error": form.errors.as_json(), "success": False}, status=400)

    return JsonResponse({"error": _('Método inválido. Use POST com "quantidade".'), "success": False}, status=405)

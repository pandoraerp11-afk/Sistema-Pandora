# produtos/views.py
import builtins
import contextlib
import csv
import json
from datetime import timedelta
from decimal import Decimal

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

# Importações do sistema
from core.mixins import TenantRequiredMixin
from core.utils import get_current_tenant
from shared.mixins.ui_permissions import UIPermissionsMixin
from shared.services.ui_permissions import build_ui_permissions

from .forms import (
    CategoriaForm,
    ProdutoBuscaForm,
    ProdutoForm,
    ProdutoImagemForm,
    ProdutoImportForm,
)

# Importações locais
from .models import Categoria, Produto, ProdutoImagem
from .utils import generate_next_codigo


class ProdutoMixin(TenantRequiredMixin):
    """Mixin base para views de produtos com funcionalidades compartilhadas"""

    def get_tenant_filtered_queryset(self, model_class):
        """Retorna queryset filtrado por tenant"""
        tenant = get_current_tenant(self.request)
        if hasattr(model_class, "tenant"):
            return model_class.objects.filter(tenant=tenant)
        return model_class.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["module_name"] = "produtos"
        context["module_title"] = "Gestão de Produtos"
        context["tenant"] = get_current_tenant(self.request)
        return context


@login_required
def produtos_home(request):
    """Dashboard avançado do módulo de produtos com estatísticas e gráficos"""
    template_name = "produtos/produtos_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Queryset base para produtos
    produtos_qs = Produto.objects.all()  # Ajustar quando implementar multi-tenancy
    categorias_qs = Categoria.objects.all()

    # Estatísticas principais
    total_produtos = produtos_qs.count()
    produtos_ativos = produtos_qs.filter(ativo=True).count()
    produtos_inativos = produtos_qs.filter(ativo=False).count()
    total_categorias = categorias_qs.count()

    # Estatísticas de estoque
    produtos_estoque_baixo = produtos_qs.filter(estoque_atual__lte=F("estoque_minimo"), estoque_atual__gt=0).count()

    produtos_sem_estoque = produtos_qs.filter(estoque_atual=0).count()

    produtos_estoque_alto = produtos_qs.filter(estoque_atual__gte=F("estoque_maximo")).count()

    # Estatísticas financeiras
    valor_total_estoque = produtos_qs.aggregate(total=Sum(F("estoque_atual") * F("preco_custo")))["total"] or 0

    valor_medio_produto = produtos_qs.aggregate(media=Avg("preco_unitario"))["media"] or 0

    # Produtos mais recentes (últimos 7 dias)
    data_limite = timezone.now() - timedelta(days=7)
    produtos_recentes = produtos_qs.filter(data_cadastro__gte=data_limite).count()

    # Dados para gráficos
    # Produtos por categoria
    produtos_por_categoria = categorias_qs.annotate(total_produtos=Count("produto")).values("nome", "total_produtos")

    chart_categorias_labels = [item["nome"] for item in produtos_por_categoria]
    chart_categorias_data = [item["total_produtos"] for item in produtos_por_categoria]

    # Status do estoque para gráfico
    estoque_status_data = [
        produtos_estoque_baixo,
        produtos_sem_estoque,
        produtos_estoque_alto,
        total_produtos - produtos_estoque_baixo - produtos_sem_estoque - produtos_estoque_alto,
    ]

    # Produtos em destaque
    produtos_destaque = produtos_qs.filter(destaque=True)[:5]

    # Produtos com estoque baixo
    produtos_alerta_estoque = produtos_qs.filter(estoque_atual__lte=F("estoque_minimo")).order_by("estoque_atual")[:10]

    # Permissões de UI para Produtos e Categorias
    ui_perms = build_ui_permissions(
        request.user,
        tenant,
        module_key="PRODUTO",
    )
    ui_perms_categoria = build_ui_permissions(
        request.user,
        tenant,
        app_label="produtos",
        model_name="categoria",
    )

    context = {
        "titulo": "Dashboard de Produtos",
        "subtitulo": "Visão geral completa do módulo de produtos",
        "tenant": tenant,
        # Permissões de UI
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
        "ui_perms_categoria": ui_perms_categoria,
        "perms_ui_categoria": ui_perms_categoria,
        # Estatísticas principais
        "total_produtos": total_produtos,
        "produtos_ativos": produtos_ativos,
        "produtos_inativos": produtos_inativos,
        "total_categorias": total_categorias,
        "produtos_recentes": produtos_recentes,
        # Estatísticas de estoque
        "produtos_estoque_baixo": produtos_estoque_baixo,
        "produtos_sem_estoque": produtos_sem_estoque,
        "produtos_estoque_alto": produtos_estoque_alto,
        # Estatísticas financeiras
        "valor_total_estoque": valor_total_estoque,
        "valor_medio_produto": valor_medio_produto,
        # Dados para gráficos
        "chart_categorias_labels": json.dumps(chart_categorias_labels),
        "chart_categorias_data": json.dumps(chart_categorias_data),
        "estoque_status_labels": json.dumps(["Estoque Baixo", "Sem Estoque", "Estoque Alto", "Normal"]),
        "estoque_status_data": json.dumps(estoque_status_data),
        # Listas para widgets
        "produtos_destaque": produtos_destaque,
        "produtos_alerta_estoque": produtos_alerta_estoque,
        # Percentuais para cards
        "percentual_ativos": (produtos_ativos / total_produtos * 100) if total_produtos > 0 else 0,
        "percentual_estoque_baixo": (produtos_estoque_baixo / total_produtos * 100) if total_produtos > 0 else 0,
    }

    return render(request, template_name, context)


class ProdutoListView(UIPermissionsMixin, ProdutoMixin, ListView):
    """Lista de produtos com busca avançada e filtros"""

    model = Produto
    template_name = "produtos/produto_list.html"
    context_object_name = "produtos"
    paginate_by = 20
    ordering = ["-data_cadastro"]
    app_label = "produtos"
    model_name = "produto"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Busca por nome ou código
        busca = self.request.GET.get("busca")
        if busca:
            queryset = queryset.filter(
                Q(nome__icontains=busca)
                | Q(codigo__icontains=busca)
                | Q(codigo_barras__icontains=busca)
                | Q(descricao__icontains=busca)
            )

        # Filtro por categoria
        categoria = self.request.GET.get("categoria")
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)

        # Filtro por status ativo/inativo
        ativo = self.request.GET.get("ativo")
        if ativo == "1":
            queryset = queryset.filter(ativo=True)
        elif ativo == "0":
            queryset = queryset.filter(ativo=False)

        # Filtro por estoque
        estoque = self.request.GET.get("estoque")
        if estoque == "baixo":
            queryset = queryset.filter(estoque_atual__lte=F("estoque_minimo"))
        elif estoque == "zerado":
            queryset = queryset.filter(estoque_atual=0)
        elif estoque == "alto":
            queryset = queryset.filter(estoque_atual__gte=F("estoque_maximo"))

        # Filtro por preço
        preco_min = self.request.GET.get("preco_min")
        if preco_min:
            with contextlib.suppress(builtins.BaseException):
                queryset = queryset.filter(preco_unitario__gte=Decimal(preco_min))

        preco_max = self.request.GET.get("preco_max")
        if preco_max:
            with contextlib.suppress(builtins.BaseException):
                queryset = queryset.filter(preco_unitario__lte=Decimal(preco_max))

        # Filtro por destaque
        destaque = self.request.GET.get("destaque")
        if destaque == "1":
            queryset = queryset.filter(destaque=True)

        # Ordenação
        ordenar = self.request.GET.get("ordenar")
        if ordenar == "nome":
            queryset = queryset.order_by("nome")
        elif ordenar == "preco_asc":
            queryset = queryset.order_by("preco_unitario")
        elif ordenar == "preco_desc":
            queryset = queryset.order_by("-preco_unitario")
        elif ordenar == "estoque":
            queryset = queryset.order_by("estoque_atual")
        elif ordenar == "categoria":
            queryset = queryset.order_by("categoria__nome")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Dados para filtros
        context["categorias"] = Categoria.objects.all().order_by("nome")
        context["form_busca"] = ProdutoBuscaForm(self.request.GET)

        # Estatísticas da listagem atual
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["ativo_count"] = queryset.filter(ativo=True).count()
        context["inativo_count"] = queryset.filter(ativo=False).count()
        context["destaque_count"] = queryset.filter(destaque=True).count()

        # Valores para resumo
        context["valor_total"] = queryset.aggregate(total=Sum(F("estoque_atual") * F("preco_unitario")))["total"] or 0

        # Cards de estatísticas no padrão ultra-moderno (usados pelo template base)
        context["statistics"] = [
            {
                "value": context["total_count"],
                "label": _("Total de Produtos"),
                "icon": "fas fa-boxes",
                "bg": "bg-gradient-primary",
                "text_color": "text-primary",
                "url": reverse("produtos:produto_list"),
            },
            {
                "value": context["ativo_count"],
                "label": _("Ativos"),
                "icon": "fas fa-check-circle",
                "bg": "bg-gradient-success",
                "text_color": "text-success",
                "url": f"{reverse('produtos:produto_list')}?ativo=1",
            },
            {
                "value": context["inativo_count"],
                "label": _("Inativos"),
                "icon": "fas fa-user-slash",
                "bg": "bg-gradient-secondary",
                "text_color": "text-secondary",
                "url": f"{reverse('produtos:produto_list')}?ativo=0",
            },
            {
                "value": context["destaque_count"],
                "label": _("Em Destaque"),
                "icon": "fas fa-star",
                "bg": "bg-gradient-warning",
                "text_color": "text-warning",
                "url": f"{reverse('produtos:produto_list')}?destaque=1",
            },
        ]

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": None, "active": True},
        ]

        # Parâmetros de filtro atuais (para manter nos links de paginação)
        context["current_filters"] = self.request.GET.urlencode()

        # Permissões adicionais: categorias (para ações de categorias no topo)
        tenant = get_current_tenant(self.request)
        ui_perms_categoria = build_ui_permissions(
            self.request.user,
            tenant,
            app_label="produtos",
            model_name="categoria",
        )
        context["ui_perms_categoria"] = ui_perms_categoria
        context["perms_ui_categoria"] = ui_perms_categoria

        return context


class ProdutoDetailView(UIPermissionsMixin, ProdutoMixin, DetailView):
    """Detalhes de um produto com informações completas"""

    model = Produto
    template_name = "produtos/produto_detail_ultra_modern.html"
    context_object_name = "produto"
    app_label = "produtos"
    model_name = "produto"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Relacionados
        context["imagens"] = self.object.imagens.all().order_by("ordem")
        context["variacoes"] = self.object.variacoes.filter(ativo=True)
        context["documentos"] = self.object.documentos.all().order_by("titulo")

        # Cálculos
        context["valor_total_estoque"] = self.object.estoque_atual * self.object.preco_unitario
        context["valor_custo_estoque"] = self.object.estoque_atual * self.object.preco_custo
        context["margem_valor"] = self.object.preco_unitario - self.object.preco_custo

        # Status do estoque
        if self.object.estoque_atual <= 0:
            context["estoque_status"] = "danger"
            context["estoque_texto"] = "Sem Estoque"
        elif self.object.estoque_atual <= self.object.estoque_minimo:
            context["estoque_status"] = "warning"
            context["estoque_texto"] = "Estoque Baixo"
        elif self.object.estoque_atual >= self.object.estoque_maximo:
            context["estoque_status"] = "info"
            context["estoque_texto"] = "Estoque Alto"
        else:
            context["estoque_status"] = "success"
            context["estoque_texto"] = "Estoque Normal"

        # Produtos relacionados (mesma categoria)
        context["produtos_relacionados"] = Produto.objects.filter(categoria=self.object.categoria, ativo=True).exclude(
            pk=self.object.pk
        )[:6]

        # Breadcrumbs
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": reverse("produtos:produto_list")},
            {"title": self.object.nome, "url": None, "active": True},
        ]

        return context


class ProdutoCreateView(UIPermissionsMixin, ProdutoMixin, CreateView):
    """Criação de novos produtos"""

    model = Produto
    form_class = ProdutoForm
    template_name = "produtos/produto_form.html"
    success_url = reverse_lazy("produtos:produto_list")
    app_label = "produtos"
    model_name = "produto"

    # Formset para múltiplas imagens
    ImagemFormSet = inlineformset_factory(
        Produto, ProdutoImagem, form=ProdutoImagemForm, fields=("imagem", "titulo", "ordem"), extra=3, can_delete=True
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_name"] = "Produto"
        form = context.get("form")

        # Formset de imagens
        if self.request.method == "POST":
            context["imagens_formset"] = self.ImagemFormSet(self.request.POST, self.request.FILES)
        else:
            context["imagens_formset"] = self.ImagemFormSet()

        # Título e breadcrumbs para o base de formulário
        context["title"] = "Cadastrar Produto"
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": reverse("produtos:produto_list")},
            {"title": "Cadastrar", "url": None, "active": True},
        ]

        # Prévia compacta com código gerado automaticamente (somente visual)
        preview_items = []
        try:
            codigo_preview = generate_next_codigo()
            if codigo_preview:
                preview_items.append(("Código (gerado)", codigo_preview))
        except Exception:
            pass
        if form:
            nome_val = (form.data.get("nome") if hasattr(form, "data") else None) or form.initial.get("nome")
            categoria_val = None
            if form.fields.get("categoria"):
                try:
                    categoria_val = form.data.get("categoria") if hasattr(form, "data") else None
                except Exception:
                    categoria_val = None
            if nome_val:
                preview_items.append(("Nome", nome_val))
            if categoria_val:
                preview_items.append(("Categoria", categoria_val))

        context["preview"] = {
            "title": "Prévia",
            "text": "Preencha os dados principais para visualizar um resumo aqui.",
            "items": preview_items,
        }
        context["form_tips"] = [
            "Informe nome, categoria e preço de venda primeiro.",
        ]
        return context

    def form_valid(self, form):
        imagens_formset = self.ImagemFormSet(self.request.POST, self.request.FILES)
        if not imagens_formset.is_valid():
            return self.form_invalid_with_formset(form, imagens_formset)

        # Tentar salvar com geração automática de código, se não informado
        try:
            with transaction.atomic():
                if not form.cleaned_data.get("codigo"):
                    form.instance.codigo = generate_next_codigo()
                self.object = form.save()
                imagens_formset.instance = self.object
                imagens_formset.save()
        except IntegrityError:
            # Em caso raro de colisão de código, gera novamente e tenta mais uma vez
            with transaction.atomic():
                form.instance.codigo = generate_next_codigo()
                self.object = form.save()
                imagens_formset.instance = self.object
                imagens_formset.save()

        messages.success(self.request, f'Produto "{self.object.nome}" criado com sucesso!')
        return redirect(self.get_success_url())

    def form_invalid_with_formset(self, form, imagens_formset):
        context = self.get_context_data(form=form)
        context["imagens_formset"] = imagens_formset
        return self.render_to_response(context)

    # Removido método duplicado de get_context_data (acima já define título e breadcrumbs)


class ProdutoUpdateView(UIPermissionsMixin, ProdutoMixin, UpdateView):
    """Atualização de produtos existentes"""

    model = Produto
    form_class = ProdutoForm
    template_name = "produtos/produto_form.html"
    app_label = "produtos"
    model_name = "produto"

    # Reutiliza o mesmo formset de imagens
    ImagemFormSet = ProdutoCreateView.ImagemFormSet

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_name"] = "Produto"
        if self.request.method == "POST":
            context["imagens_formset"] = self.ImagemFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context["imagens_formset"] = self.ImagemFormSet(instance=self.object)
        # Título e breadcrumbs para o base de formulário
        context["title"] = f"Editar Produto - {self.object.nome}"
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": reverse("produtos:produto_list")},
            {"title": self.object.nome, "url": reverse("produtos:produto_detail", kwargs={"pk": self.object.pk})},
            {"title": "Editar", "url": None, "active": True},
        ]
        # Ativa layout estreito (col-lg-8) fornecendo preview e dicas
        context["preview"] = {
            "title": "Resumo",
            "items": [
                ("Código", self.object.codigo or "-"),
                ("Nome", self.object.nome),
                ("Categoria", getattr(self.object.categoria, "nome", "-")),
                ("Preço", getattr(self.object, "preco_unitario", 0)),
                ("Estoque", getattr(self.object, "estoque_atual", 0)),
            ],
        }
        context["form_tips"] = [
            "Revise preços e estoque antes de salvar.",
        ]
        return context

    def form_valid(self, form):
        imagens_formset = self.ImagemFormSet(self.request.POST, self.request.FILES, instance=self.object)
        if not imagens_formset.is_valid():
            return self.form_invalid_with_formset(form, imagens_formset)

        with transaction.atomic():
            self.object = form.save()
            imagens_formset.save()

        messages.success(self.request, f'Produto "{self.object.nome}" atualizado com sucesso!')
        return redirect(self.object.get_absolute_url())

    def form_invalid_with_formset(self, form, imagens_formset):
        context = self.get_context_data(form=form)
        context["imagens_formset"] = imagens_formset
        return self.render_to_response(context)

    # Removido método duplicado de get_context_data (acima já define título e breadcrumbs)


class ProdutoDeleteView(UIPermissionsMixin, ProdutoMixin, DeleteView):
    """Exclusão de produtos"""

    model = Produto
    template_name = "produtos/produto_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("produtos:produto_list")
    app_label = "produtos"
    model_name = "produto"

    def delete(self, request, *args, **kwargs):
        produto = self.get_object()
        messages.success(request, f'Produto "{produto.nome}" excluído com sucesso!')
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": reverse("produtos:produto_list")},
            {"title": self.object.nome, "url": reverse("produtos:produto_detail", kwargs={"pk": self.object.pk})},
            {"title": "Excluir", "url": None, "active": True},
        ]
        return context


# Views para Categorias
class CategoriaListView(UIPermissionsMixin, ProdutoMixin, ListView):
    """Lista de categorias de produtos"""

    model = Categoria
    template_name = "produtos/categoria_list_ultra_modern.html"
    context_object_name = "categorias"
    paginate_by = 20
    ordering = ["nome"]
    app_label = "produtos"
    model_name = "categoria"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Anotar com contagem de produtos
        queryset = queryset.annotate(total_produtos=Count("produto"))

        # Busca
        busca = self.request.GET.get("busca")
        if busca:
            queryset = queryset.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))

        # Filtro por status
        ativo = self.request.GET.get("ativo")
        if ativo == "1":
            queryset = queryset.filter(ativo=True)
        elif ativo == "0":
            queryset = queryset.filter(ativo=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Produtos", "url": reverse("produtos:produto_list")},
            {"title": "Categorias", "url": None, "active": True},
        ]
        return context


class CategoriaCreateView(UIPermissionsMixin, ProdutoMixin, CreateView):
    """Criação de categorias"""

    model = Categoria
    form_class = CategoriaForm
    template_name = "produtos/categoria_form_ultra_modern.html"
    success_url = reverse_lazy("produtos:categoria_list")
    app_label = "produtos"
    model_name = "categoria"

    def form_valid(self, form):
        # form.instance.tenant = get_current_tenant(self.request)  # Quando implementar multi-tenancy
        messages.success(self.request, f'Categoria "{form.instance.nome}" criada com sucesso!')
        return super().form_valid(form)


class CategoriaUpdateView(UIPermissionsMixin, ProdutoMixin, UpdateView):
    """Atualização de categorias"""

    model = Categoria
    form_class = CategoriaForm
    template_name = "produtos/categoria_form_ultra_modern.html"
    success_url = reverse_lazy("produtos:categoria_list")
    app_label = "produtos"
    model_name = "categoria"

    def form_valid(self, form):
        messages.success(self.request, f'Categoria "{form.instance.nome}" atualizada com sucesso!')
        return super().form_valid(form)


class CategoriaDeleteView(UIPermissionsMixin, ProdutoMixin, DeleteView):
    """Exclusão de categorias"""

    model = Categoria
    template_name = "produtos/categoria_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("produtos:categoria_list")
    app_label = "produtos"
    model_name = "categoria"

    def delete(self, request, *args, **kwargs):
        categoria = self.get_object()
        messages.success(request, f'Categoria "{categoria.nome}" excluída com sucesso!')
        return super().delete(request, *args, **kwargs)


# Views AJAX para operações rápidas
@login_required
def produto_toggle_ativo(request, pk):
    """Toggle do status ativo de um produto via AJAX"""
    if request.method == "POST":
        produto = get_object_or_404(Produto, pk=pk)
        produto.ativo = not produto.ativo
        produto.save()

        return JsonResponse(
            {
                "success": True,
                "ativo": produto.ativo,
                "message": f"Produto {'ativado' if produto.ativo else 'desativado'} com sucesso!",
            }
        )

    return JsonResponse({"success": False, "message": "Método não permitido"})


@login_required
def produto_toggle_destaque(request, pk):
    """Toggle do destaque de um produto via AJAX"""
    if request.method == "POST":
        produto = get_object_or_404(Produto, pk=pk)
        produto.destaque = not produto.destaque
        produto.save()

        return JsonResponse(
            {
                "success": True,
                "destaque": produto.destaque,
                "message": f"Produto {'adicionado aos' if produto.destaque else 'removido dos'} destaques!",
            }
        )

    return JsonResponse({"success": False, "message": "Método não permitido"})


@login_required
def produtos_search_ajax(request):
    """Busca de produtos via AJAX para autocomplete"""
    term = request.GET.get("term", "")

    produtos = Produto.objects.filter(
        Q(nome__icontains=term) | Q(codigo__icontains=term) | Q(codigo_barras__icontains=term)
    ).filter(ativo=True)[:10]

    results = []
    for produto in produtos:
        results.append(
            {
                "id": produto.id,
                "label": produto.nome,
                "value": produto.nome,
                "codigo": produto.codigo or "",
                "preco": float(produto.preco_unitario),
                "estoque": produto.estoque_atual,
            }
        )

    return JsonResponse(results, safe=False)


# Views para exportação
@login_required
def produto_export_csv(request):
    """Exporta produtos para CSV"""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="produtos.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Código",
            "Nome",
            "Categoria",
            "Preço Unitário",
            "Preço Custo",
            "Estoque Atual",
            "Estoque Mínimo",
            "Estoque Máximo",
            "Ativo",
        ]
    )

    produtos = Produto.objects.select_related("categoria").all()
    for produto in produtos:
        writer.writerow(
            [
                produto.codigo or "",
                produto.nome,
                produto.categoria.nome,
                produto.preco_unitario,
                produto.preco_custo,
                produto.estoque_atual,
                produto.estoque_minimo,
                produto.estoque_maximo,
                "Sim" if produto.ativo else "Não",
            ]
        )

    return response


@login_required
def produto_export_excel(request):
    """Exporta produtos para Excel"""
    produtos = Produto.objects.select_related("categoria").all()

    data = []
    for produto in produtos:
        data.append(
            {
                "Código": produto.codigo or "",
                "Nome": produto.nome,
                "Categoria": produto.categoria.nome,
                "Preço Unitário": float(produto.preco_unitario),
                "Preço Custo": float(produto.preco_custo),
                "Estoque Atual": produto.estoque_atual,
                "Estoque Mínimo": produto.estoque_minimo,
                "Estoque Máximo": produto.estoque_maximo,
                "Ativo": "Sim" if produto.ativo else "Não",
            }
        )

    df = pd.DataFrame(data)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="produtos.xlsx"'

    df.to_excel(response, index=False, engine="openpyxl")

    return response


# Views para importação
@login_required
def produto_import(request):
    """Importa produtos de arquivo CSV/Excel"""
    if request.method == "POST":
        form = ProdutoImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES["arquivo"]

            try:
                df = pd.read_csv(arquivo) if arquivo.name.endswith(".csv") else pd.read_excel(arquivo)

                importados = 0
                erros = []

                for index, row in df.iterrows():
                    try:
                        # Buscar ou criar categoria
                        categoria_nome = row.get("Categoria", "").strip()
                        if categoria_nome:
                            categoria, created = Categoria.objects.get_or_create(
                                nome=categoria_nome, defaults={"descricao": f"Categoria importada: {categoria_nome}"}
                            )
                        else:
                            categoria = None

                        # Criar produto
                        produto = Produto(
                            nome=row.get("Nome", "").strip(),
                            codigo=row.get("Código", "").strip() or None,
                            categoria=categoria,
                            preco_unitario=float(row.get("Preço Unitário", 0)),
                            preco_custo=float(row.get("Preço Custo", 0)),
                            estoque_atual=int(row.get("Estoque Atual", 0)),
                            estoque_minimo=int(row.get("Estoque Mínimo", 0)),
                            estoque_maximo=int(row.get("Estoque Máximo", 0)),
                        )
                        produto.save()
                        importados += 1

                    except Exception as e:
                        erros.append(f"Linha {index + 2}: {str(e)}")

                if importados > 0:
                    messages.success(request, f"{importados} produtos importados com sucesso!")

                if erros:
                    for erro in erros[:5]:  # Mostrar apenas os primeiros 5 erros
                        messages.warning(request, erro)

            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
    else:
        form = ProdutoImportForm()

    return render(
        request,
        "produtos/produto_import_ultra_modern.html",
        {
            "form": form,
            "breadcrumbs": [
                {"title": "Dashboard", "url": reverse("dashboard")},
                {"title": "Produtos", "url": reverse("produtos:produto_list")},
                {"title": "Importar", "url": None, "active": True},
            ],
        },
    )

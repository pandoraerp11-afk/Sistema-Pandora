from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tables2 import RequestConfig

from cadastros_gerais.models import ItemAuxiliar
from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import FornecedorDocumentoVersaoCreateForm
from .models import (
    Fornecedor,
    FornecedorDocumento,
)

# Removido: formulários e formsets antigos de criação/edição; o cadastro usa apenas o Wizard
from .tables import FornecedorTable


@login_required
def fornecedor_list(request):
    tenant_atual = get_current_tenant(request)
    user = request.user
    is_global_view = user.is_superuser and not tenant_atual

    if is_global_view:
        queryset = Fornecedor.objects.all().select_related("pessoafisica", "pessoajuridica", "tenant", "categoria")
        subtitle = _("Visão Global de Todos os Fornecedores")
    elif tenant_atual:
        queryset = Fornecedor.objects.filter(tenant=tenant_atual).select_related(
            "pessoafisica", "pessoajuridica", "categoria"
        )
        subtitle = _("Gestão de Fornecedores")
    else:
        messages.error(request, _("Nenhuma empresa selecionada."))
        return redirect("core:tenant_select")

    table = FornecedorTable(queryset)
    if not is_global_view:
        table.exclude = ("tenant",)

    RequestConfig(request, paginate={"per_page": 20}).configure(table)
    # Fornece também 'object_list' e paginação básica para o template moderno
    page_number = request.GET.get("page")
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page_number)
    object_list = page_obj.object_list

    # Estatísticas esperadas pelo template moderno (nomes de chaves compatíveis)
    total_fornecedores = queryset.count()
    fornecedores_ativos = queryset.filter(status="active").count()
    fornecedores_preferenciais = 0  # Placeholder se não houver flag específica
    novos_mes = queryset.filter(data_cadastro__gte=timezone.now() - timedelta(days=30)).count()

    ui_perms = build_ui_permissions(request.user, tenant_atual, module_key="FORNECEDOR")

    context = {
        "table": table,
        "object_list": object_list,
        "is_paginated": page_obj.paginator.num_pages > 1,
        "page_obj": page_obj,
        "titulo": _("Fornecedores"),
        "subtitulo": subtitle,
        "add_url": reverse("fornecedores:fornecedor_wizard"),
        "module": "fornecedores",
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
        # Estatísticas para o template ultra-moderno
        "statistics": [
            {
                "value": total_fornecedores,
                "label": _("Total de Fornecedores"),
                "icon": "fas fa-truck",
                "bg": "bg-gradient-primary",
                "text_color": "text-primary",
            },
            {
                "value": fornecedores_ativos,
                "label": _("Fornecedores Ativos"),
                "icon": "fas fa-check-circle",
                "bg": "bg-gradient-success",
                "text_color": "text-success",
            },
            {
                "value": fornecedores_preferenciais,
                "label": _("Preferenciais"),
                "icon": "fas fa-star",
                "bg": "bg-gradient-info",
                "text_color": "text-info",
            },
            {
                "value": novos_mes,
                "label": _("Novos este Mês"),
                "icon": "fas fa-calendar",
                "bg": "bg-gradient-warning",
                "text_color": "text-warning",
            },
        ],
        # Breadcrumbs
        "breadcrumbs": [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Fornecedores", "url": None, "active": True},
        ],
    }
    return render(request, "fornecedores/fornecedores_list.html", context)


@login_required
def fornecedor_detail(request, pk):
    user = request.user
    query_args = {"pk": pk}
    if not user.is_superuser:
        query_args["tenant"] = get_current_tenant(request)

    fornecedor = get_object_or_404(Fornecedor.objects.select_related("pessoafisica", "pessoajuridica"), **query_args)

    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, module_key="FORNECEDOR")

    context = {
        "fornecedor": fornecedor,
        "titulo": f"Fornecedor: {fornecedor}",
        "subtitulo": "Detalhes do Fornecedor",
        "module": "fornecedores",
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
        # Breadcrumbs
        "breadcrumbs": [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Fornecedores", "url": reverse("fornecedores:fornecedores_list")},
            {"title": str(fornecedor), "url": None, "active": True},
        ],
    }
    return render(request, "fornecedores/fornecedores_detail.html", context)


@login_required
def fornecedor_create(request):
    """Compat: redireciona criação para o Wizard canônico."""
    from .wizard_views import fornecedor_wizard_create

    return fornecedor_wizard_create(request)


@login_required
def fornecedor_edit(request, pk):
    """Compat: redireciona edição para o Wizard canônico de edição."""
    from .wizard_views import fornecedor_wizard_edit

    return fornecedor_wizard_edit(request, pk)


@login_required
def fornecedor_delete(request, pk):
    query_args = {"pk": pk}
    if not request.user.is_superuser:
        query_args["tenant"] = get_current_tenant(request)

    fornecedor = get_object_or_404(Fornecedor, **query_args)
    # Checagem de permissão UI/ação (server-side continua tendo verificação por tenant)
    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, module_key="FORNECEDOR")
    if not (request.user.is_superuser or ui_perms.get("can_delete")):
        messages.error(request, _("Você não tem permissão para excluir fornecedores."))
        return redirect("fornecedores:fornecedores_list")

    if request.method == "POST":
        fornecedor.delete()
        messages.success(request, _("Fornecedor excluído com sucesso."))
    return redirect("fornecedores:fornecedores_list")

    context = {"fornecedor": fornecedor, "titulo": "Confirmar Exclusão"}
    return render(request, "fornecedores/fornecedores_confirm_delete.html", context)


@login_required
def fornecedores_home(request):
    """
    View para o dashboard de fornecedores, mostrando estatísticas e dados relevantes.
    """
    template_name = "fornecedores/fornecedores_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Deferimos campos recém-adicionados para mitigar erro em bancos sem migração aplicada
    fornecedores_qs = Fornecedor.objects.filter(tenant=tenant).defer(
        "regioes_atendidas",
        "prazo_pagamento_dias",
        "pedido_minimo",
        "prazo_medio_entrega_dias",
    )

    # Estatísticas
    total_fornecedores = fornecedores_qs.count()
    ativos = fornecedores_qs.filter(status="active").count()
    pendentes_homologacao = fornecedores_qs.filter(status_homologacao="pendente").count()
    media_avaliacao = fornecedores_qs.filter(avaliacao__isnull=False).aggregate(Avg("avaliacao"))["avaliacao__avg"] or 0

    # Novos fornecedores (últimos 30 dias)
    data_limite = datetime.now() - timedelta(days=30)
    novos_fornecedores_qs = fornecedores_qs.filter(data_cadastro__gte=data_limite)

    # Top 5 Categorias
    top_categorias = (
        Fornecedor.objects.filter(tenant=tenant, categoria__isnull=False)
        .values("categoria__nome")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # Permissões de UI para Fornecedor
    ui_perms = build_ui_permissions(request.user, tenant, module_key="FORNECEDOR")

    context = {
        "page_title": _("Dashboard de Fornecedores"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_fornecedores": total_fornecedores,
        "fornecedores_ativos": ativos,
        "pendentes_homologacao": pendentes_homologacao,
        "media_avaliacao": f"{media_avaliacao:.1f}",
        "novos_fornecedores_count": novos_fornecedores_qs.count(),
        "fornecedores_recentes": novos_fornecedores_qs.order_by("-data_cadastro")[:5],
        "top_categorias": top_categorias,
        "fornecedores_por_status": list(fornecedores_qs.values("status").annotate(total=Count("id"))),
        # UI Perms
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


@login_required
def fornecedor_documents(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    tenant = get_current_tenant(request)
    if not request.user.is_superuser and fornecedor.tenant_id != getattr(tenant, "id", None):
        messages.error(request, _("Acesso negado."))
        return redirect("fornecedores:fornecedores_list")

    if request.method == "POST":
        form = FornecedorDocumentoVersaoCreateForm(request.POST, request.FILES, fornecedor=fornecedor)
        if form.is_valid():
            versao = form.save(user=request.user)
            messages.success(request, _("Documento enviado com sucesso (v%(v)s).") % {"v": versao.versao})
            return redirect("fornecedores:fornecedor_documents", pk=fornecedor.pk)
        else:
            messages.error(request, _("Corrija os erros abaixo."))
    else:
        form = FornecedorDocumentoVersaoCreateForm(fornecedor=fornecedor)

    tipos_qs = ItemAuxiliar.objects.filter(ativo=True)
    tipos_qs = tipos_qs.filter(models.Q(alvo="fornecedor") | models.Q(targets__code="fornecedor")).distinct()
    tipos_qs = tipos_qs.select_related("categoria").order_by("categoria__ordem", "ordem", "nome")

    categorias = {}
    tipo_doc_map = {}
    for tipo in tipos_qs:
        cat = tipo.categoria
        categorias.setdefault(cat, []).append(tipo)
        # Mapeia o documento do fornecedor para cada tipo
        tipo_doc_map[tipo.pk] = FornecedorDocumento.objects.filter(fornecedor=fornecedor, tipo=tipo).first()

    historico_por_tipo = {}
    for tipo in tipos_qs:
        doc = tipo_doc_map.get(tipo.pk)
        historico_por_tipo[tipo.pk] = list(doc.versoes.order_by("-enviado_em", "-versao")[:5]) if doc else []

    # Adiciona o documento do fornecedor ao tipo para uso no template
    for tipo in tipos_qs:
        tipo.documento_fornecedor = tipo_doc_map.get(tipo.pk)

    context = {
        "fornecedor": fornecedor,
        "categorias": categorias,
        "historico_por_tipo": historico_por_tipo,
        "form_nova_versao": form,
    }
    return render(request, "fornecedores/fornecedor_documents.html", context)

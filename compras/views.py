# compras/views.py
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_tables2 import RequestConfig

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import CompraForm  # Se você tiver um CompraForm, importe-o aqui também
from .models import Compra  # Se você tiver um modelo Cotacao, importe-o aqui também
from .tables import CompraTable  # Se você tiver uma CotacaoTable, importe-a aqui também


@login_required
def compras_home(request):
    """
    View para o dashboard de compras, mostrando estatísticas e dados relevantes.
    """
    template_name = "compras/compras_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Assumindo que Compra está ligada a um Tenant através da Obra
    compras_qs = Compra.objects.filter(obra__tenant=tenant)

    # Estatísticas
    total_compras = compras_qs.count()
    total_gasto = compras_qs.aggregate(Sum("valor_total"))["valor_total__sum"] or 0
    status_counts = dict(compras_qs.values_list("status").annotate(total=Count("status")))

    data_limite = datetime.now() - timedelta(days=30)
    novas_compras_qs = compras_qs.filter(data_pedido__gte=data_limite)

    top_fornecedores = compras_qs.values("fornecedor__nome_fantasia").annotate(total=Count("id")).order_by("-total")[:5]

    ui_perms = build_ui_permissions(request.user, tenant, app_label="compras", model_name="compra")

    context = {
        "page_title": _("Dashboard de Compras"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_compras": total_compras,
        "total_gasto": f"{total_gasto:,.2f}",
        "compras_pendentes": status_counts.get("pendente", 0),
        "compras_entregues": status_counts.get("entregue", 0),
        "compras_recentes_count": novas_compras_qs.count(),
        "compras_recentes": novas_compras_qs.order_by("-data_pedido")[:5],
        "status_data": [status_counts.get(s[0], 0) for s in Compra.status.field.choices],
        "status_labels": [s[1] for s in Compra.status.field.choices],
        "top_fornecedores": top_fornecedores,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


@login_required
def compra_list(request):
    """
    Exibe a lista de compras com suporte a ordenação, filtragem e paginação.
    Utiliza django-tables2 para renderização avançada da tabela.
    """
    compras = Compra.objects.all()
    table = CompraTable(compras)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    return render(
        request,
        "compras/compras_list_ultra_modern.html",
        {
            "table": table,
            "titulo": "Compras",
            "subtitulo": "Gerenciamento de Compras",
            "add_url": reverse("compras:compras_create"),
            "module": "compras",
        },
    )


@login_required
def compra_detail(request, pk):
    """
    Exibe os detalhes de uma compra específica.
    """
    compra = get_object_or_404(Compra, pk=pk)

    return render(
        request,
        "compras/compras_detail_ultra_modern.html",
        {
            "compra": compra,
            "titulo": f"Compra: {compra.numero}",
            "subtitulo": "Detalhes da Compra",
            "module": "compras",
        },
    )


@login_required
def compra_add(request):
    """
    Adiciona uma nova compra.
    """
    if request.method == "POST":
        form = CompraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Compra adicionada com sucesso!")
            return redirect("compras:compras_list")
    else:
        form = CompraForm()

    return render(
        request,
        "compras/compras_form_ultra_modern.html",
        {"form": form, "titulo": "Adicionar Compra", "subtitulo": "Nova Compra", "module": "compras"},
    )


@login_required
def compra_edit(request, pk):
    """
    Edita uma compra existente.
    """
    compra = get_object_or_404(Compra, pk=pk)

    if request.method == "POST":
        form = CompraForm(request.POST, instance=compra)
        if form.is_valid():
            compra = form.save()
            messages.success(request, "Compra atualizada com sucesso!")
            return redirect("compras:compras_list")
    else:
        form = CompraForm(instance=compra)

    return render(
        request,
        "compras/compras_form_ultra_modern.html",
        {
            "form": form,
            "compra": compra,
            "titulo": f"Editar Compra: {compra.numero}",
            "subtitulo": "Editar Compra",
            "module": "compras",
        },
    )


@login_required
def compra_delete(request, pk):
    """
    Exclui uma compra existente.
    """
    compra = get_object_or_404(Compra, pk=pk)

    if request.method == "POST":
        compra.delete()
        messages.success(request, "Compra excluída com sucesso!")
        return redirect("compras:compras_list")

    return render(
        request,
        "compras/compras_confirm_delete_ultra_modern.html",
        {
            "compra": compra,
            "titulo": f"Excluir Compra: {compra.numero}",
            "subtitulo": "Confirmar Exclusão",
            "module": "compras",
        },
    )


# NOVA VIEW ADICIONADA ABAIXO
@login_required
def cotacoes_list(request):
    """
    Exibe a lista de cotações.
    (Implementação de exemplo - ajuste conforme suas necessidades)
    """
    # Exemplo: Supondo que você tenha um modelo chamado 'Cotacao'
    # from .models import Cotacao
    # cotacoes = Cotacao.objects.all()
    # table = CotacaoTable(cotacoes) # Supondo que você crie uma CotacaoTable
    # RequestConfig(request, paginate={"per_page": 10}).configure(table)

    context = {
        # 'table': table, # Descomente quando tiver a lógica da tabela
        "titulo": "Cotações",
        "subtitulo": "Lista de Cotações de Compras",
        "module": "compras",
        # 'add_url': reverse('compras:cotacao_create'), # Se você tiver uma URL para criar cotação
    }
    # Você precisará criar o template 'compras/cotacoes_list_ultra_modern.html'
    return render(request, "compras/cotacoes_list_ultra_modern.html", context)

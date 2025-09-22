from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tables2 import RequestConfig

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import ContaPagarForm, ContaReceberForm, FinanceiroForm
from .models import ContaPagar, ContaReceber, Financeiro
from .tables import ContaPagarTable, ContaReceberTable, FinanceiroTable


@login_required
@login_required
def financeiro_home(request):
    """
    View para o dashboard de Financeiro, mostrando estatísticas e dados relevantes.
    """
    template_name = "financeiro/financeiro_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    ui_perms = build_ui_permissions(request.user, tenant, app_label="financeiro", model_name="financeiro")

    context = {
        "titulo": _("Financeiro"),
        "subtitulo": _("Visão geral do módulo Financeiro"),
        "tenant": tenant,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }

    return render(request, template_name, context)


def financeiro_list(request):
    """
    Exibe a lista de movimentações financeiras com suporte a ordenação, filtragem e paginação.
    Utiliza django-tables2 para renderização avançada da tabela.
    """
    # Obter todas as movimentações financeiras
    financeiros = Financeiro.objects.all()

    # Criar tabela usando django-tables2
    table = FinanceiroTable(financeiros)

    # Configurar paginação e ordenação
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    # Variáveis para templates ultra-modernos
    from datetime import datetime, timedelta

    thirty_days_ago = datetime.now() - timedelta(days=30)

    # Renderizar template com a tabela
    return render(
        request,
        "financeiro/financeiro_list_ultra_modern.html",
        {
            "table": table,
            "titulo": "Financeiro",
            "subtitulo": "Gerenciamento Financeiro",
            "add_url": reverse("financeiro:financeiro_add"),
            "module": "financeiro",
            # Variáveis para templates ultra-modernos
            "total_count": financeiros.count(),
            "active_count": financeiros.filter(ativo=True).count()
            if hasattr(Financeiro, "ativo")
            else financeiros.count(),
            "inactive_count": financeiros.filter(ativo=False).count() if hasattr(Financeiro, "ativo") else 0,
            "recent_count": financeiros.filter(data__gte=thirty_days_ago).count(),
            # Breadcrumbs
            "breadcrumbs": [
                {"title": "Dashboard", "url": reverse("dashboard")},
                {"title": "Financeiro", "url": None, "active": True},
            ],
        },
    )


@login_required
def financeiro_detail(request, pk):
    """
    Exibe os detalhes de uma movimentação financeira específica.
    """
    # Obter movimentação pelo ID ou retornar 404
    financeiro = get_object_or_404(Financeiro, pk=pk)

    # Renderizar template com os detalhes da movimentação
    return render(
        request,
        "financeiro/financeiro_detail_ultra_modern.html",
        {
            "financeiro": financeiro,
            "titulo": f"Movimentação: {financeiro.descricao}",
            "subtitulo": "Detalhes da Movimentação",
            "module": "financeiro",
            # Breadcrumbs
            "breadcrumbs": [
                {"title": "Dashboard", "url": reverse("dashboard")},
                {"title": "Financeiro", "url": reverse("financeiro:financeiro_list")},
                {"title": financeiro.descricao, "url": None, "active": True},
            ],
        },
    )


@login_required
def financeiro_add(request):
    """
    Adiciona uma nova movimentação financeira.
    """
    if request.method == "POST":
        # Processar formulário enviado
        form = FinanceiroForm(request.POST)
        if form.is_valid():
            # Salvar movimentação
            form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Movimentação adicionada com sucesso!")
            # Redirecionar para a lista de movimentações
            return redirect("financeiro:financeiro_list")
    else:
        # Exibir formulário vazio
        form = FinanceiroForm()

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/financeiro_form_ultra_modern.html",
        {"form": form, "titulo": "Adicionar Movimentação", "subtitulo": "Nova Movimentação", "module": "financeiro"},
    )


@login_required
def financeiro_edit(request, pk):
    """
    Edita uma movimentação financeira existente.
    """
    # Obter movimentação pelo ID ou retornar 404
    financeiro = get_object_or_404(Financeiro, pk=pk)

    if request.method == "POST":
        # Processar formulário enviado
        form = FinanceiroForm(request.POST, instance=financeiro)
        if form.is_valid():
            # Salvar alterações
            financeiro = form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Movimentação atualizada com sucesso!")
            # Redirecionar para a lista de movimentações
            return redirect("financeiro:financeiro_list")
    else:
        # Exibir formulário preenchido com os dados da movimentação
        form = FinanceiroForm(instance=financeiro)

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/financeiro_form_ultra_modern.html",
        {
            "form": form,
            "financeiro": financeiro,
            "titulo": f"Editar Movimentação: {financeiro.descricao}",
            "subtitulo": "Editar Movimentação",
            "module": "financeiro",
        },
    )


@login_required
def financeiro_delete(request, pk):
    """
    Exclui uma movimentação financeira existente.
    """
    # Obter movimentação pelo ID ou retornar 404
    financeiro = get_object_or_404(Financeiro, pk=pk)

    if request.method == "POST":
        # Excluir movimentação
        financeiro.delete()
        # Exibir mensagem de sucesso
        messages.success(request, "Movimentação excluída com sucesso!")
        # Redirecionar para a lista de movimentações
        return redirect("financeiro:financeiro_list")

    # Renderizar template de confirmação
    return render(
        request,
        "financeiro/financeiro_confirm_delete_ultra_modern.html",
        {
            "financeiro": financeiro,
            "titulo": f"Excluir Movimentação: {financeiro.descricao}",
            "subtitulo": "Confirmar Exclusão",
            "module": "financeiro",
        },
    )


# Views para Contas a Pagar


@login_required
def conta_pagar_list(request):
    """
    Exibe a lista de contas a pagar com suporte a ordenação, filtragem e paginação.
    """
    # Obter todas as contas a pagar
    contas = ContaPagar.objects.all()

    # Criar tabela usando django-tables2
    table = ContaPagarTable(contas)

    # Configurar paginação e ordenação
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    # Renderizar template com a tabela
    return render(
        request,
        "financeiro/conta_pagar_list_ultra_modern.html",
        {
            "table": table,
            "titulo": "Contas a Pagar",
            "subtitulo": "Gerenciamento de Contas a Pagar",
            "add_url": reverse("financeiro:conta_pagar_add"),
            "module": "financeiro",
        },
    )


@login_required
def conta_pagar_detail(request, pk):
    """
    Exibe os detalhes de uma conta a pagar específica.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaPagar, pk=pk)

    # Renderizar template com os detalhes da conta
    return render(
        request,
        "financeiro/conta_pagar_detail_ultra_modern.html",
        {
            "conta": conta,
            "titulo": f"Conta a Pagar: {conta.descricao}",
            "subtitulo": "Detalhes da Conta a Pagar",
            "module": "financeiro",
        },
    )


@login_required
def conta_pagar_add(request):
    """
    Adiciona uma nova conta a pagar.
    """
    if request.method == "POST":
        # Processar formulário enviado
        form = ContaPagarForm(request.POST)
        if form.is_valid():
            # Salvar conta
            form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Conta a pagar adicionada com sucesso!")
            # Redirecionar para a lista de contas
            return redirect("financeiro:conta_pagar_list")
    else:
        # Exibir formulário vazio
        form = ContaPagarForm()

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/conta_pagar_form_ultra_modern.html",
        {"form": form, "titulo": "Adicionar Conta a Pagar", "subtitulo": "Nova Conta a Pagar", "module": "financeiro"},
    )


@login_required
def conta_pagar_edit(request, pk):
    """
    Edita uma conta a pagar existente.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaPagar, pk=pk)

    if request.method == "POST":
        # Processar formulário enviado
        form = ContaPagarForm(request.POST, instance=conta)
        if form.is_valid():
            # Salvar alterações
            conta = form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Conta a pagar atualizada com sucesso!")
            # Redirecionar para a lista de contas
            return redirect("financeiro:conta_pagar_list")
    else:
        # Exibir formulário preenchido com os dados da conta
        form = ContaPagarForm(instance=conta)

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/conta_pagar_form_ultra_modern.html",
        {
            "form": form,
            "conta": conta,
            "titulo": f"Editar Conta a Pagar: {conta.descricao}",
            "subtitulo": "Editar Conta a Pagar",
            "module": "financeiro",
        },
    )


@login_required
def conta_pagar_delete(request, pk):
    """
    Exclui uma conta a pagar existente.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaPagar, pk=pk)

    if request.method == "POST":
        # Excluir conta
        conta.delete()
        # Exibir mensagem de sucesso
        messages.success(request, "Conta a pagar excluída com sucesso!")
        # Redirecionar para a lista de contas
        return redirect("financeiro:conta_pagar_list")

    # Renderizar template de confirmação
    return render(
        request,
        "financeiro/conta_pagar_confirm_delete_ultra_modern.html",
        {
            "conta": conta,
            "titulo": f"Excluir Conta a Pagar: {conta.descricao}",
            "subtitulo": "Confirmar Exclusão",
            "module": "financeiro",
        },
    )


@login_required
def conta_pagar_pagar(request, pk):
    """
    Marca uma conta a pagar como paga.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaPagar, pk=pk)

    # Marcar como paga
    conta.status = "pago"
    conta.data_pagamento = timezone.now().date()
    conta.save()

    # Exibir mensagem de sucesso
    messages.success(request, "Conta marcada como paga com sucesso!")

    # Redirecionar para a lista de contas
    return redirect("financeiro:conta_pagar_list")


# Views para Contas a Receber


@login_required
def conta_receber_list(request):
    """
    Exibe a lista de contas a receber com suporte a ordenação, filtragem e paginação.
    """
    # Obter todas as contas a receber
    contas = ContaReceber.objects.all()

    # Criar tabela usando django-tables2
    table = ContaReceberTable(contas)

    # Configurar paginação e ordenação
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    # Renderizar template com a tabela
    return render(
        request,
        "financeiro/conta_receber_list_ultra_modern.html",
        {
            "table": table,
            "titulo": "Contas a Receber",
            "subtitulo": "Gerenciamento de Contas a Receber",
            "add_url": reverse("financeiro:conta_receber_add"),
            "module": "financeiro",
        },
    )


@login_required
def conta_receber_detail(request, pk):
    """
    Exibe os detalhes de uma conta a receber específica.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaReceber, pk=pk)

    # Renderizar template com os detalhes da conta
    return render(
        request,
        "financeiro/conta_receber_detail_ultra_modern.html",
        {
            "conta": conta,
            "titulo": f"Conta a Receber: {conta.descricao}",
            "subtitulo": "Detalhes da Conta a Receber",
            "module": "financeiro",
        },
    )


@login_required
def conta_receber_add(request):
    """
    Adiciona uma nova conta a receber.
    """
    if request.method == "POST":
        # Processar formulário enviado
        form = ContaReceberForm(request.POST)
        if form.is_valid():
            # Salvar conta
            form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Conta a receber adicionada com sucesso!")
            # Redirecionar para a lista de contas
            return redirect("financeiro:conta_receber_list")
    else:
        # Exibir formulário vazio
        form = ContaReceberForm()

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/conta_receber_form_ultra_modern.html",
        {
            "form": form,
            "titulo": "Adicionar Conta a Receber",
            "subtitulo": "Nova Conta a Receber",
            "module": "financeiro",
        },
    )


@login_required
def conta_receber_edit(request, pk):
    """
    Edita uma conta a receber existente.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaReceber, pk=pk)

    if request.method == "POST":
        # Processar formulário enviado
        form = ContaReceberForm(request.POST, instance=conta)
        if form.is_valid():
            # Salvar alterações
            conta = form.save()
            # Exibir mensagem de sucesso
            messages.success(request, "Conta a receber atualizada com sucesso!")
            # Redirecionar para a lista de contas
            return redirect("financeiro:conta_receber_list")
    else:
        # Exibir formulário preenchido com os dados da conta
        form = ContaReceberForm(instance=conta)

    # Renderizar template com o formulário
    return render(
        request,
        "financeiro/conta_receber_form_ultra_modern.html",
        {
            "form": form,
            "conta": conta,
            "titulo": f"Editar Conta a Receber: {conta.descricao}",
            "subtitulo": "Editar Conta a Receber",
            "module": "financeiro",
        },
    )


@login_required
def conta_receber_delete(request, pk):
    """
    Exclui uma conta a receber existente.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaReceber, pk=pk)

    if request.method == "POST":
        # Excluir conta
        conta.delete()
        # Exibir mensagem de sucesso
        messages.success(request, "Conta a receber excluída com sucesso!")
        # Redirecionar para a lista de contas
        return redirect("financeiro:conta_receber_list")

    # Renderizar template de confirmação
    return render(
        request,
        "financeiro/conta_receber_confirm_delete_ultra_modern.html",
        {
            "conta": conta,
            "titulo": f"Excluir Conta a Receber: {conta.descricao}",
            "subtitulo": "Confirmar Exclusão",
            "module": "financeiro",
        },
    )


@login_required
def conta_receber_receber(request, pk):
    """
    Marca uma conta a receber como recebida.
    """
    # Obter conta pelo ID ou retornar 404
    conta = get_object_or_404(ContaReceber, pk=pk)

    # Marcar como recebida
    conta.status = "recebido"
    conta.data_recebimento = timezone.now().date()
    conta.save()

    # Exibir mensagem de sucesso
    messages.success(request, "Conta marcada como recebida com sucesso!")

    # Redirecionar para a lista de contas
    return redirect("financeiro:conta_receber_list")

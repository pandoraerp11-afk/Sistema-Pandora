"""Views de Clientes (versão consolidada e limpa).

Este arquivo contém as views para o módulo de Clientes, com o seguinte escopo:
  - Dashboard: clientes_home
  - Listagem: ClienteListView
  - Detalhe: ClienteDetailView
  - Exclusão: ClienteDeleteView
  - Importação: cliente_import
  - APIs (AJAX): api_cliente_search, api_cliente_stats

As views de criação (Create) e atualização (Update) foram removidas deste arquivo
pois essa funcionalidade agora é gerenciada pelo wizard em 'wizard_views.py'.
Views duplicadas e código obsoleto foram removidos para clareza e manutenção.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, cast

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, DetailView, ListView

from core.mixins import TenantRequiredMixin
from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import ClienteImportForm
from .models import Cliente, PessoaFisica, PessoaJuridica

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.core.files.uploadedfile import UploadedFile
    from django.forms import Form

    from core.models import Tenant


# Constantes
DIAS_RECENTES = 30
MIN_SEARCH_LENGTH = 2


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required
def clientes_home(request: HttpRequest) -> HttpResponse:
    """Exibe o dashboard de clientes com estatísticas agregadas."""
    tenant = get_current_tenant(request)
    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    qs = Cliente.objects.filter(tenant=tenant)
    data_limite = datetime.now(UTC) - timedelta(days=DIAS_RECENTES)
    novos_qs = qs.filter(data_cadastro__gte=data_limite)

    pf_count = qs.filter(tipo="PF").count()
    pj_count = qs.filter(tipo="PJ").count()
    total_tipo = (pf_count or 0) + (pj_count or 0)
    pf_percent = round((pf_count / total_tipo) * 100) if total_tipo else 0
    pj_percent = 100 - pf_percent if total_tipo else 0

    ui_perms = build_ui_permissions(cast("User", request.user), tenant, app_label="clientes", model_name="cliente")

    context = {
        "page_title": _("Dashboard de Clientes"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_clientes": qs.count(),
        "clientes_ativos": qs.filter(status="active").count(),
        "clientes_inativos": qs.filter(status="inactive").count(),
        "clientes_suspensos": qs.filter(status="suspended").count(),
        "novos_clientes_30d": novos_qs.count(),
        "clientes_recentes": novos_qs.order_by("-data_cadastro")[:5],
        "total_pf": pf_count,
        "total_pj": pj_count,
        "pf_percent": pf_percent,
        "pj_percent": pj_percent,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,  # Alias legado
    }
    return render(request, "clientes/clientes_home.html", context)


# ---------------------------------------------------------------------------
# Mixin e Views de CRUD
# ---------------------------------------------------------------------------


class ClienteMixin(TenantRequiredMixin):
    """Mixin base para views de Cliente, garantindo o isolamento por tenant."""

    def get_queryset(self) -> QuerySet[Cliente]:
        """Filtra o queryset pelo tenant do usuário logado."""
        return super().get_queryset().filter(tenant=self.request.tenant)


class ClienteListView(ClienteMixin, ListView):
    """View para listar e filtrar clientes."""

    model = Cliente
    template_name = "clientes/clientes_list.html"
    context_object_name = "clientes"
    paginate_by = 25

    def get_queryset(self) -> QuerySet[Cliente]:
        """Aplica filtros de busca, tipo, status e cidade ao queryset."""
        qs = super().get_queryset().select_related("pessoafisica", "pessoajuridica")
        search = self.request.GET.get("search")
        tipo = self.request.GET.get("tipo")
        status = self.request.GET.get("status")
        cidade = self.request.GET.get("cidade")

        if search:
            qs = qs.filter(
                Q(pessoafisica__nome_completo__icontains=search)
                | Q(pessoajuridica__razao_social__icontains=search)
                | Q(pessoajuridica__nome_fantasia__icontains=search)
                | Q(pessoafisica__cpf__icontains=search)
                | Q(pessoajuridica__cnpj__icontains=search)
                | Q(email__icontains=search)
                | Q(telefone__icontains=search),
            ).distinct()
        if tipo:
            qs = qs.filter(tipo=tipo)
        if status:
            qs = qs.filter(status=status)
        if cidade:
            qs = qs.filter(cidade__icontains=cidade)
        return qs.order_by("-data_cadastro")


class ClienteDetailView(ClienteMixin, DetailView):
    """View para exibir os detalhes de um cliente."""

    model = Cliente
    # Usando template existente. O antigo "_ultra_modern" não foi criado e causava TemplateDoesNotExist.
    template_name = "clientes/clientes_detail.html"
    context_object_name = "cliente"

    def get_queryset(self) -> QuerySet[Cliente]:
        """Otimiza a query para incluir dados de pessoa física e jurídica."""
        return super().get_queryset().select_related("pessoafisica", "pessoajuridica")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Adiciona dados extras ao contexto para exibição no template.

        Usa o método correto de super() e tipagem restrita (object) para evitar Any.
        """
        context = super().get_context_data(**kwargs)
        cliente: Cliente = self.object
        context.update(
            {
                "page_title": "Detalhes do Cliente",
                "page_subtitle": cliente.nome_display,
                "pessoa_fisica": getattr(cliente, "pessoafisica", None),
                "pessoa_juridica": getattr(cliente, "pessoajuridica", None),
                "contatos": cliente.contatos_adicionais.all(),
                "enderecos": cliente.enderecos_adicionais.all(),
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {"title": cliente.nome_display, "url": None, "active": True},
                ],
                "can_edit": True,
                "can_delete": True,
                "edit_url": reverse("clientes:clientes_update", kwargs={"pk": cliente.pk}),
                "delete_url": reverse("clientes:clientes_delete", kwargs={"pk": cliente.pk}),
                "list_url": reverse("clientes:clientes_list"),
            },
        )
        return context


class ClienteDeleteView(ClienteMixin, DeleteView):
    """View para confirmar e executar a exclusão de um cliente."""

    model = Cliente
    # Ajustado para template existente (remove sufixo _ultra_modern inexistente)
    template_name = "clientes/clientes_confirm_delete.html"
    context_object_name = "cliente"
    success_url = reverse_lazy("clientes:clientes_list")

    def get_object(self, queryset: QuerySet[Cliente] | None = None) -> Cliente:
        """Garante que o usuário só possa excluir clientes do seu próprio tenant."""
        obj = cast("Cliente", super().get_object(queryset))
        if not self.request.user.is_superuser and obj.tenant != self.request.tenant:
            msg = "Cliente não encontrado"
            raise Http404(msg)
        return obj

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Adiciona dados ao contexto para a página de confirmação."""
        context = super().get_context_data(**kwargs)
        cliente: Cliente = self.object
        context.update(
            {
                "page_title": "Excluir Cliente",
                "page_subtitle": f"Confirmação de exclusão: {cliente.nome_display}",
                "delete_message": f'Tem certeza que deseja excluir o cliente "{cliente.nome_display}"?',
                "warning_message": "Esta ação não pode ser desfeita e todos os dados relacionados serão perdidos.",
                "cancel_url": reverse("clientes:clientes_detail", kwargs={"pk": cliente.pk}),
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {
                        "title": cliente.nome_display,
                        "url": reverse("clientes:clientes_detail", kwargs={"pk": cliente.pk}),
                    },
                    {"title": "Excluir", "url": None, "active": True},
                ],
            },
        )
        return context

    def form_valid(self, form: Form) -> HttpResponse:
        """Processa a exclusão e trata possíveis erros de integridade."""
        cliente_nome = self.object.nome_display
        try:
            response = super().form_valid(form)
        except IntegrityError as e:
            messages.error(self.request, f'Não foi possível excluir o cliente "{cliente_nome}". Erro: {e!s}')
            return redirect("clientes:clientes_list")
        else:
            messages.success(self.request, f'Cliente "{cliente_nome}" excluído com sucesso!')
            return response


# ---------------------------------------------------------------------------
# Funcionalidades Adicionais (Importação)
# ---------------------------------------------------------------------------


def _read_file_to_dataframe(arquivo: UploadedFile) -> pd.DataFrame | None:
    """Lê um arquivo CSV ou Excel em memória retornando DataFrame.

    Evita passar UploadedFile diretamente (pyright incompatibilidade) convertendo
    para buffer apropriado. Retorna None se formato não suportado ou parsing falhar.
    """
    nome = (arquivo.name or "").lower()
    try:
        if nome.endswith(".csv"):
            # CSV: decodifica para texto antes de passar ao pandas
            content = arquivo.read()
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("latin-1", errors="ignore")
            return pd.read_csv(StringIO(text))
        if nome.endswith((".xlsx", ".xls")):
            # Excel: pandas aceita bytes buffer
            content = arquivo.read()
            return pd.read_excel(BytesIO(content))
    except (ValueError, OSError, pd.errors.EmptyDataError, pd.errors.ParserError):  # pragma: no cover - robustez
        return None
    return None


def _process_cliente_row(row: pd.Series, tenant: Tenant) -> Cliente:
    """Cria um objeto Cliente e seus dados relacionados (PF/PJ) a partir de uma linha do DataFrame."""
    cliente = Cliente(
        tenant=tenant,
        tipo=row.get("tipo", "PF").upper(),
        email=row.get("email", ""),
        telefone=row.get("telefone", ""),
        logradouro=row.get("logradouro", ""),
        numero=row.get("numero", ""),
        bairro=row.get("bairro", ""),
        cidade=row.get("cidade", ""),
        estado=row.get("estado", ""),
        cep=row.get("cep", ""),
        status="active",
    )
    cliente.save()

    if cliente.tipo == "PF":
        PessoaFisica.objects.create(
            cliente=cliente,
            nome_completo=row.get("nome", ""),
            cpf=row.get("cpf", ""),
            rg=row.get("rg", ""),
            data_nascimento=row.get("data_nascimento") if pd.notna(row.get("data_nascimento")) else None,
        )
    else:
        PessoaJuridica.objects.create(
            cliente=cliente,
            razao_social=row.get("nome", ""),
            nome_fantasia=row.get("nome_fantasia", ""),
            cnpj=row.get("cnpj", ""),
            inscricao_estadual=row.get("inscricao_estadual", ""),
        )
    return cliente


@login_required
@transaction.atomic
def cliente_import(request: HttpRequest) -> HttpResponse:
    """Processa a importação de clientes em massa via arquivo CSV ou Excel."""
    tenant = get_current_tenant(request)
    if not tenant:
        messages.error(request, _("Nenhuma empresa selecionada."))
        return redirect("core:tenant_select")

    form = ClienteImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arquivo = form.cleaned_data["arquivo"]
        df = _read_file_to_dataframe(arquivo)

        if df is None:
            messages.error(request, _("Formato de arquivo não suportado. Use CSV ou Excel."))
            return redirect("clientes:cliente_import")

        try:
            total_criados = 0
            for _index, row in df.iterrows():
                _process_cliente_row(row, tenant)
                total_criados += 1
            messages.success(request, _("%d clientes importados com sucesso!") % total_criados)
        except (ValueError, KeyError, TypeError) as exc:
            messages.error(request, _("Ocorreu um erro durante a importação: %s") % str(exc))

        return redirect("clientes:clientes_list")

    ui_perms = build_ui_permissions(cast("User", request.user), tenant, app_label="clientes", model_name="cliente")
    context = {
        "form": form,
        "page_title": _("Importar Clientes"),
        "page_subtitle": _("Importe clientes em massa a partir de um arquivo CSV ou Excel."),
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, "clientes/cliente_import.html", context)


# ---------------------------------------------------------------------------
# API Views (para AJAX)
# ---------------------------------------------------------------------------


@login_required
def api_cliente_search(request: HttpRequest) -> JsonResponse:
    """Busca clientes para preenchimento de selects com AJAX."""
    query = request.GET.get("q", "")
    if len(query) < MIN_SEARCH_LENGTH:
        return JsonResponse({"results": []})

    tenant_atual = get_current_tenant(request)
    if request.user.is_superuser and not tenant_atual:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(tenant=tenant_atual)

    clientes = clientes.filter(
        Q(pessoafisica__nome_completo__icontains=query)
        | Q(pessoajuridica__razao_social__icontains=query)
        | Q(pessoajuridica__nome_fantasia__icontains=query)
        | Q(email__icontains=query),
    ).select_related("pessoafisica", "pessoajuridica")[:10]

    results = [
        {
            "id": c.id,
            "text": f"{c.nome_display} ({c.email})",
            "tipo": c.get_tipo_display(),
            "status": c.get_status_display(),
        }
        for c in clientes
    ]
    return JsonResponse({"results": results})


@login_required
def api_cliente_stats(request: HttpRequest) -> JsonResponse:
    """Fornece estatísticas de clientes para dashboards ou widgets."""
    tenant_atual = get_current_tenant(request)
    if request.user.is_superuser and not tenant_atual:
        queryset = Cliente.objects.all()
    else:
        queryset = Cliente.objects.filter(tenant=tenant_atual)

    data_recente = datetime.now(UTC) - timedelta(days=DIAS_RECENTES)
    stats = {
        "total_clientes": queryset.count(),
        "clientes_ativos": queryset.filter(status="active").count(),
        "clientes_pf": queryset.filter(tipo="PF").count(),
        "clientes_pj": queryset.filter(tipo="PJ").count(),
        "clientes_recentes": queryset.filter(data_cadastro__gte=data_recente).count(),
        "por_cidade": list(queryset.values("cidade").annotate(total=Count("id")).order_by("-total")[:10]),
        "por_status": list(queryset.values("status").annotate(total=Count("id")).order_by("status")),
    }
    return JsonResponse(stats)

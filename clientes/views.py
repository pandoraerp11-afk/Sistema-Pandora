# clientes/views.py (VERSÃO ULTRA-MODERNA CORRIGIDA)

from datetime import datetime, timedelta

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import TenantRequiredMixin

# Importação da função utilitária para pegar o tenant atual
from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions

from .forms import (
    ClienteBaseForm,
    ClienteImportForm,
    ContatoFormSet,
    DocumentoClienteFormSet,
    EnderecoAdicionalFormSet,
    PessoaFisicaForm,
    PessoaJuridicaForm,
)

# Modelos e Formulários
from .models import Cliente, DocumentoCliente, PessoaFisica, PessoaJuridica


@login_required
def clientes_home(request):
    """
    View para o dashboard de clientes, mostrando estatísticas e dados relevantes.
    """
    template_name = "clientes/clientes_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    # Queryset base
    clientes_qs = Cliente.objects.filter(tenant=tenant)

    # Estatísticas principais
    total_clientes = clientes_qs.count()
    ativos = clientes_qs.filter(status="active").count()
    inativos = clientes_qs.filter(status="inactive").count()
    suspensos = clientes_qs.filter(status="suspended").count()

    # Novos clientes (últimos 30 dias)
    data_limite = datetime.now() - timedelta(days=30)
    novos_clientes_qs = clientes_qs.filter(data_cadastro__gte=data_limite)

    # Breakdown por tipo
    pf_count = clientes_qs.filter(tipo="PF").count()
    pj_count = clientes_qs.filter(tipo="PJ").count()
    total_tipo = (pf_count or 0) + (pj_count or 0)
    pf_percent = int(round((pf_count / total_tipo) * 100)) if total_tipo else 0
    pj_percent = 100 - pf_percent if total_tipo else 0

    ui_perms = build_ui_permissions(request.user, tenant, app_label="clientes", model_name="cliente")

    context = {
        "page_title": _("Dashboard de Clientes"),
        "page_subtitle": "Visão geral e estatísticas do módulo",
        "total_clientes": total_clientes,
        "clientes_ativos": ativos,
        "clientes_inativos": inativos,
        "clientes_suspensos": suspensos,
        "novos_clientes_30d": novos_clientes_qs.count(),
        "clientes_recentes": novos_clientes_qs.order_by("-data_cadastro")[:5],
        "total_pf": pf_count,
        "total_pj": pj_count,
        "pf_percent": pf_percent,
        "pj_percent": pj_percent,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, template_name, context)


class ClienteMixin(TenantRequiredMixin):
    """Mixin base para views de clientes"""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)

    def form_valid(self, form):
        if hasattr(form.instance, "tenant"):
            form.instance.tenant = self.request.tenant
        return super().form_valid(form)


class ClienteListView(ClienteMixin, ListView):
    model = Cliente
    template_name = "clientes/clientes_list.html"
    context_object_name = "clientes"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related("pessoafisica", "pessoajuridica")

        # Filtros
        search = self.request.GET.get("search")
        tipo = self.request.GET.get("tipo")
        status = self.request.GET.get("status")
        cidade = self.request.GET.get("cidade")

        if search:
            queryset = queryset.filter(
                Q(pessoafisica__nome_completo__icontains=search)
                | Q(pessoajuridica__razao_social__icontains=search)
                | Q(pessoajuridica__nome_fantasia__icontains=search)
                | Q(pessoafisica__cpf__icontains=search)
                | Q(pessoajuridica__cnpj__icontains=search)
                | Q(email__icontains=search)
                | Q(telefone__icontains=search)
            ).distinct()

        if tipo:
            queryset = queryset.filter(tipo=tipo)

        if status:
            queryset = queryset.filter(status=status)

        if cidade:
            queryset = queryset.filter(cidade__icontains=cidade)

        return queryset.order_by("-data_cadastro")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Contexto ultra-moderno
        context.update(
            {
                "page_title": "Clientes",
                "page_subtitle": "Gestão completa de clientes",
                "search_query": self.request.GET.get("search", ""),
                "tipo_filter": self.request.GET.get("tipo", ""),
                "status_filter": self.request.GET.get("status", ""),
                "cidade_filter": self.request.GET.get("cidade", ""),
                # Estatísticas
                "total_count": queryset.count(),
                "active_count": queryset.filter(status="active").count(),
                "inactive_count": queryset.filter(status__in=["inactive", "suspended"]).count(),
                "recent_count": queryset.filter(data_cadastro__gte=datetime.now() - timedelta(days=30)).count(),
                "pf_count": queryset.filter(tipo="PF").count(),
                "pj_count": queryset.filter(tipo="PJ").count(),
                # Estatísticas para cards do topo (padronizado com pandora_list_ultra_modern)
                "statistics": [
                    {
                        "value": queryset.count(),
                        "label": _("Total de Clientes"),
                        "icon": "fas fa-users",
                        "bg": "bg-gradient-primary",
                        "text_color": "text-primary",
                        "url": reverse("clientes:clientes_list"),
                    },
                    {
                        "value": queryset.filter(status="active").count(),
                        "label": _("Clientes Ativos"),
                        "icon": "fas fa-user-check",
                        "bg": "bg-gradient-success",
                        "text_color": "text-success",
                        "url": f"{reverse('clientes:clientes_list')}?status=active",
                    },
                    {
                        "value": queryset.filter(status__in=["inactive", "suspended"]).count(),
                        "label": _("Inativos/Suspensos"),
                        "icon": "fas fa-user-slash",
                        "bg": "bg-gradient-secondary",
                        "text_color": "text-secondary",
                        "url": f"{reverse('clientes:clientes_list')}?status=inactive",
                    },
                    {
                        "value": queryset.filter(data_cadastro__gte=datetime.now() - timedelta(days=30)).count(),
                        "label": _("Novos (30 dias)"),
                        "icon": "fas fa-user-plus",
                        "bg": "bg-gradient-warning",
                        "text_color": "text-warning",
                        "url": f"{reverse('clientes:clientes_list')}?recent=1",
                    },
                ],
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": None, "active": True},
                ],
                # Botões de ação
                "can_add": True,
                "can_edit": True,
                "can_delete": True,
                "can_import": True,
                "add_url": reverse("clientes:clientes_create"),
                "import_url": reverse("clientes:cliente_import"),
                # Choices para filtros
                "tipo_choices": Cliente.TIPO_CHOICES,
                "status_choices": Cliente.STATUS_CHOICES,
            }
        )

        return context


def placeholder_view(request):
    """Placeholder view to fix decorator error. Replace with actual implementation."""
    return JsonResponse({"message": "This is a placeholder. Implement your view here."})


def cliente_detail(request, pk):
    tenant_atual = get_current_tenant(request)
    # MODIFICAÇÃO SUTIL PARA A VISÃO GLOBAL: Superadmin pode ver qualquer cliente.
    query_args = {"pk": pk}
    if not request.user.is_superuser:
        query_args["tenant"] = tenant_atual  # Força o filtro de tenant para não-superadmins.

    cliente = get_object_or_404(Cliente.objects.select_related("pessoafisica", "pessoajuridica"), **query_args)

    pessoa_fisica = getattr(cliente, "pessoafisica", None)
    pessoa_juridica = getattr(cliente, "pessoajuridica", None)

    contatos = cliente.contatos_adicionais.all()
    enderecos = cliente.enderecos_adicionais.all()
    documentos = cliente.documentos_cliente.all()

    return render(
        request,
        "clientes/clientes_detail_ultra_modern.html",
        {
            "cliente": cliente,
            "pessoa_fisica": pessoa_fisica,
            "pessoa_juridica": pessoa_juridica,
            "contatos": contatos,
            "enderecos": enderecos,
            "documentos": documentos,
            "titulo": f"{_('Cliente')}: {cliente.nome_display}",
            "subtitulo": _("Detalhes do Cliente"),
            "module": "clientes",
            # Breadcrumbs
            "breadcrumbs": [
                {"title": "Dashboard", "url": reverse("dashboard")},
                {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                {"title": cliente.nome_display, "url": None, "active": True},
            ],
        },
    )


class ClienteCreateView(
    ClienteMixin, CreateView
):  # DEPRECATED: substituído pelo wizard (manter até confirmar ausência de reverses indiretos)
    model = Cliente
    template_name = "clientes/clientes_form_ultra_modern.html"
    form_class = ClienteBaseForm
    success_url = reverse_lazy("clientes:clientes_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Inicializar formulários PF/PJ
        if self.request.POST:
            context["form_pf"] = PessoaFisicaForm(self.request.POST, prefix="pf", tenant=self.request.tenant)
            context["form_pj"] = PessoaJuridicaForm(self.request.POST, prefix="pj", tenant=self.request.tenant)
            context["contato_formset"] = ContatoFormSet(self.request.POST, prefix="contatos")
            context["endereco_formset"] = EnderecoAdicionalFormSet(self.request.POST, prefix="enderecos")
            context["documento_formset"] = DocumentoClienteFormSet(self.request.POST, prefix="documentos")
        else:
            context["form_pf"] = PessoaFisicaForm(prefix="pf", tenant=self.request.tenant)
            context["form_pj"] = PessoaJuridicaForm(prefix="pj", tenant=self.request.tenant)
            context["contato_formset"] = ContatoFormSet(prefix="contatos")
            context["endereco_formset"] = EnderecoAdicionalFormSet(prefix="enderecos")
            context["documento_formset"] = DocumentoClienteFormSet(prefix="documentos")

        # Renomear o form principal
        context["cliente_form"] = context["form"]

        # Contexto ultra-moderno
        context.update(
            {
                "page_title": "Novo Cliente",
                "page_subtitle": "Cadastrar novo cliente",
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {"title": "Novo Cliente", "url": None, "active": True},
                ],
            }
        )

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        form_pf = context["form_pf"]
        form_pj = context["form_pj"]
        contato_formset = context["contato_formset"]
        endereco_formset = context["endereco_formset"]
        documento_formset = context["documento_formset"]

        # Validar formulários baseado no tipo
        tipo_cliente = form.cleaned_data.get("tipo")
        forms_to_validate = [form, contato_formset, endereco_formset, documento_formset]
        active_form = None

        if tipo_cliente == "PF":
            forms_to_validate.append(form_pf)
            active_form = form_pf
        elif tipo_cliente == "PJ":
            forms_to_validate.append(form_pj)
            active_form = form_pj

        if all(f.is_valid() for f in forms_to_validate):
            with transaction.atomic():
                # Salvar cliente
                form.instance.tenant = self.request.tenant
                self.object = form.save()

                # Salvar dados específicos PF/PJ
                if active_form:
                    related_instance = active_form.save(commit=False)
                    related_instance.cliente = self.object
                    related_instance.save()

                # Salvar formsets
                for formset in [contato_formset, endereco_formset, documento_formset]:
                    if formset.is_valid():
                        instances = formset.save(commit=False)
                        for instance in instances:
                            instance.cliente = self.object
                            instance.save()
                        formset.save_m2m()

                messages.success(self.request, "Cliente criado com sucesso!")
                return redirect(self.object.get_absolute_url())

        return self.form_invalid(form)


class ClienteUpdateView(ClienteMixin, UpdateView):  # DEPRECATED: substituído pelo wizard
    model = Cliente
    template_name = "clientes/clientes_form_ultra_modern.html"
    form_class = ClienteBaseForm

    def get_object(self):
        obj = super().get_object()
        # Verificar se o usuário tem permissão para editar este cliente
        if not self.request.user.is_superuser and obj.tenant != self.request.tenant:
            raise Http404("Cliente não encontrado")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Instâncias relacionadas
        pessoa_fisica_instance = getattr(self.object, "pessoafisica", None)
        pessoa_juridica_instance = getattr(self.object, "pessoajuridica", None)

        # Inicializar formulários PF/PJ
        if self.request.POST:
            context["form_pf"] = PessoaFisicaForm(
                self.request.POST, instance=pessoa_fisica_instance, prefix="pf", tenant=self.object.tenant
            )
            context["form_pj"] = PessoaJuridicaForm(
                self.request.POST, instance=pessoa_juridica_instance, prefix="pj", tenant=self.object.tenant
            )
            context["contato_formset"] = ContatoFormSet(self.request.POST, instance=self.object, prefix="contatos")
            context["endereco_formset"] = EnderecoAdicionalFormSet(
                self.request.POST, instance=self.object, prefix="enderecos"
            )
            context["documento_formset"] = DocumentoClienteFormSet(
                self.request.POST, instance=self.object, prefix="documentos"
            )
        else:
            context["form_pf"] = PessoaFisicaForm(
                instance=pessoa_fisica_instance, prefix="pf", tenant=self.object.tenant
            )
            context["form_pj"] = PessoaJuridicaForm(
                instance=pessoa_juridica_instance, prefix="pj", tenant=self.object.tenant
            )
            context["contato_formset"] = ContatoFormSet(instance=self.object, prefix="contatos")
            context["endereco_formset"] = EnderecoAdicionalFormSet(instance=self.object, prefix="enderecos")
            context["documento_formset"] = DocumentoClienteFormSet(instance=self.object, prefix="documentos")

        # Renomear o form principal
        context["cliente_form"] = context["form"]

        # Contexto ultra-moderno
        context.update(
            {
                "page_title": f"Editar Cliente - {self.object.nome_display}",
                "page_subtitle": f"Editando informações do cliente {self.object.nome_display}",
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {
                        "title": self.object.nome_display,
                        "url": reverse("clientes:clientes_detail", args=[self.object.pk]),
                    },
                    {"title": "Editar", "url": None, "active": True},
                ],
            }
        )

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        form_pf = context["form_pf"]
        form_pj = context["form_pj"]
        contato_formset = context["contato_formset"]
        endereco_formset = context["endereco_formset"]
        documento_formset = context["documento_formset"]

        # Validar formulários baseado no tipo
        tipo_cliente = form.cleaned_data.get("tipo")
        forms_to_validate = [form, contato_formset, endereco_formset, documento_formset]
        active_form = None

        if tipo_cliente == "PF":
            forms_to_validate.append(form_pf)
            active_form = form_pf
        elif tipo_cliente == "PJ":
            forms_to_validate.append(form_pj)
            active_form = form_pj

        if all(f.is_valid() for f in forms_to_validate):
            with transaction.atomic():
                # Salvar cliente
                self.object = form.save()

                # Salvar dados específicos PF/PJ
                if active_form:
                    related_instance = active_form.save(commit=False)
                    related_instance.cliente = self.object
                    related_instance.save()

                # Salvar formsets
                for formset in [contato_formset, endereco_formset, documento_formset]:
                    if formset.is_valid():
                        instances = formset.save(commit=False)
                        for instance in instances:
                            instance.cliente = self.object
                            instance.save()
                        formset.save_m2m()

                messages.success(self.request, "Cliente atualizado com sucesso!")
                return redirect(self.object.get_absolute_url())

        return self.form_invalid(form)


class ClienteDeleteView(ClienteMixin, DeleteView):
    model = Cliente
    template_name = "clientes/clientes_confirm_delete_ultra_modern.html"
    success_url = reverse_lazy("clientes:clientes_list")

    def get_object(self):
        obj = super().get_object()
        # Verificar se o usuário tem permissão para deletar este cliente
        if not self.request.user.is_superuser and obj.tenant != self.request.tenant:
            raise Http404("Cliente não encontrado")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Excluir Cliente - {self.object.nome_display}",
                "page_subtitle": f"Confirmar exclusão do cliente {self.object.nome_display}",
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {
                        "title": self.object.nome_display,
                        "url": reverse("clientes:clientes_detail", args=[self.object.pk]),
                    },
                    {"title": "Excluir", "url": None, "active": True},
                ],
            }
        )
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        nome_cliente = self.object.nome_display
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(request, f"Cliente {nome_cliente} excluído com sucesso!")
        return redirect(success_url)


## Removidos wrappers cliente_add / cliente_edit (não expostos em urls) – consultar histórico git se necessário reativar


@login_required
def cliente_delete(request, pk):
    tenant_atual = get_current_tenant(request)
    query_args = {"pk": pk}
    if not request.user.is_superuser:
        query_args["tenant"] = tenant_atual
    cliente = get_object_or_404(Cliente, **query_args)

    if request.method == "POST":
        try:
            with transaction.atomic():
                cliente.delete()
            messages.success(request, _("Cliente excluído com sucesso!"))
            return redirect("clientes:clientes_list")
        except Exception as e:
            messages.error(request, _(f"Erro ao excluir cliente: {e}"))
            return redirect(cliente.get_absolute_url())

    return render(
        request,
        "clientes/clientes_confirm_delete_ultra_modern.html",
        {
            "cliente": cliente,
            "titulo": f"{_('Excluir Cliente')}: {cliente.nome_display}",
            "subtitulo": _("Confirmar Exclusão"),
            "module": "clientes",
        },
    )


@login_required
@transaction.atomic
def cliente_import(request):
    """View para importação de clientes via arquivo"""
    if request.method == "POST":
        form = ClienteImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                arquivo = form.cleaned_data["arquivo"]
                tenant_atual = get_current_tenant(request)

                if not tenant_atual:
                    messages.error(request, "Selecione uma empresa antes de importar clientes.")
                    return redirect("core:tenant_select")

                # Processar arquivo CSV/Excel
                if arquivo.name.endswith(".csv"):
                    df = pd.read_csv(arquivo)
                elif arquivo.name.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(arquivo)
                else:
                    messages.error(request, "Formato de arquivo não suportado. Use CSV ou Excel.")
                    return render(request, "clientes/clientes_import_ultra_modern.html", {"form": form})

                # Validar colunas obrigatórias
                colunas_obrigatorias = ["nome", "tipo", "email"]
                if not all(col in df.columns for col in colunas_obrigatorias):
                    messages.error(request, f"O arquivo deve conter as colunas: {', '.join(colunas_obrigatorias)}")
                    return render(request, "clientes/clientes_import_ultra_modern.html", {"form": form})

                clientes_criados = 0
                clientes_erro = 0

                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            # Criar cliente
                            cliente = Cliente(
                                tenant=tenant_atual,
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

                            # Criar Pessoa Física ou Jurídica
                            if cliente.tipo == "PF":
                                PessoaFisica.objects.create(
                                    cliente=cliente,
                                    nome_completo=row.get("nome", ""),
                                    cpf=row.get("cpf", ""),
                                    rg=row.get("rg", ""),
                                    data_nascimento=row.get("data_nascimento")
                                    if pd.notna(row.get("data_nascimento"))
                                    else None,
                                )
                            else:
                                PessoaJuridica.objects.create(
                                    cliente=cliente,
                                    razao_social=row.get("nome", ""),
                                    nome_fantasia=row.get("nome_fantasia", ""),
                                    cnpj=row.get("cnpj", ""),
                                    inscricao_estadual=row.get("inscricao_estadual", ""),
                                )

                            clientes_criados += 1

                        except Exception as e:
                            clientes_erro += 1
                            print(f"Erro na linha {index + 1}: {str(e)}")
                            continue

                messages.success(
                    request, f"Importação concluída! {clientes_criados} clientes criados, {clientes_erro} erros."
                )
                return redirect("clientes:clientes_list")

            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
    else:
        form = ClienteImportForm()

    context = {
        "form": form,
        "page_title": "Importar Clientes",
        "page_subtitle": "Importe clientes em massa via arquivo CSV ou Excel",
        "breadcrumbs": [
            {"title": "Dashboard", "url": reverse("dashboard")},
            {"title": "Clientes", "url": reverse("clientes:clientes_list")},
            {"title": "Importar", "url": None, "active": True},
        ],
    }

    return render(request, "clientes/clientes_import_ultra_modern.html", context)


@login_required
def documento_cliente_download(request, pk):
    """Download de documento do cliente"""
    documento = get_object_or_404(DocumentoCliente, pk=pk)

    # Verificar se o usuário tem acesso ao cliente
    tenant_atual = get_current_tenant(request)
    if not request.user.is_superuser and documento.cliente.tenant != tenant_atual:
        messages.error(request, "Acesso negado.")
        return redirect("clientes:clientes_list")

    try:
        return FileResponse(documento.arquivo.open("rb"), as_attachment=True, filename=documento.filename)
    except Exception as e:
        messages.error(request, f"Erro ao baixar arquivo: {str(e)}")
        return redirect("clientes:clientes_detail", pk=documento.cliente.pk)


# Class-Based Views Ultra-Modernas


class ClienteDetailView(ClienteMixin, DetailView):
    """View detalhada de um cliente"""

    model = Cliente
    template_name = "clientes/clientes_detail_ultra_modern.html"
    context_object_name = "cliente"

    def get_queryset(self):
        return super().get_queryset().select_related("pessoafisica", "pessoajuridica")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()

        context.update(
            {
                "page_title": "Detalhes do Cliente",
                "page_subtitle": cliente.nome_display,
                "pessoa_fisica": getattr(cliente, "pessoafisica", None),
                "pessoa_juridica": getattr(cliente, "pessoajuridica", None),
                "contatos": cliente.contatos_adicionais.all(),
                "enderecos": cliente.enderecos_adicionais.all(),
                "documentos": cliente.documentos_cliente.all(),
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {"title": cliente.nome_display, "url": None, "active": True},
                ],
                # Botões de ação
                "can_edit": True,
                "can_delete": True,
                "edit_url": reverse("clientes:clientes_update", kwargs={"pk": cliente.pk}),
                "delete_url": reverse("clientes:clientes_delete", kwargs={"pk": cliente.pk}),
                "list_url": reverse("clientes:clientes_list"),
            }
        )

        return context


class ClienteDeleteView(ClienteMixin, DeleteView):
    """View para excluir cliente"""

    model = Cliente
    template_name = "clientes/clientes_confirm_delete_ultra_modern.html"
    context_object_name = "cliente"
    success_url = reverse_lazy("clientes:clientes_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()
        context.update(
            {
                "page_title": "Excluir Cliente",
                "page_subtitle": f"Confirmação de exclusão: {cliente.nome_display}",
                "delete_message": f'Tem certeza que deseja excluir o cliente "{cliente.nome_display}"?',
                "warning_message": "Esta ação não pode ser desfeita e todos os dados relacionados serão perdidos.",
                "cancel_url": reverse("clientes:clientes_detail", kwargs={"pk": cliente.pk}),
                # Breadcrumbs
                "breadcrumbs": [
                    {"title": "Dashboard", "url": reverse("dashboard")},
                    {"title": "Clientes", "url": reverse("clientes:clientes_list")},
                    {
                        "title": cliente.nome_display,
                        "url": reverse("clientes:clientes_detail", kwargs={"pk": cliente.pk}),
                    },
                    {"title": "Excluir", "url": None, "active": True},
                ],
            }
        )
        return context

    def form_valid(self, form):
        cliente_nome = self.object.nome_display
        try:
            response = super().form_valid(form)
            messages.success(self.request, f'Cliente "{cliente_nome}" excluído com sucesso!')
            return response
        except Exception as e:
            messages.error(self.request, f'Não foi possível excluir o cliente "{cliente_nome}". Erro: {str(e)}')
            return redirect("clientes:clientes_list")


# API Views para AJAX e integrações


@login_required
def api_cliente_search(request):
    """API para busca de clientes via AJAX"""
    query = request.GET.get("q", "")
    tenant_atual = get_current_tenant(request)

    if len(query) < 2:
        return JsonResponse({"results": []})

    if request.user.is_superuser and not tenant_atual:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(tenant=tenant_atual)

    clientes = clientes.filter(
        Q(pessoafisica__nome_completo__icontains=query)
        | Q(pessoajuridica__razao_social__icontains=query)
        | Q(pessoajuridica__nome_fantasia__icontains=query)
        | Q(email__icontains=query)
    ).select_related("pessoafisica", "pessoajuridica")[:10]

    results = []
    for cliente in clientes:
        results.append(
            {
                "id": cliente.id,
                "text": f"{cliente.nome_display} ({cliente.email})",
                "tipo": cliente.get_tipo_display(),
                "documento": cliente.documento_principal,
                "status": cliente.get_status_display(),
            }
        )

    return JsonResponse({"results": results})


@login_required
def api_cliente_stats(request):
    """API para estatísticas de clientes"""
    tenant_atual = get_current_tenant(request)

    if request.user.is_superuser and not tenant_atual:
        queryset = Cliente.objects.all()
    else:
        queryset = Cliente.objects.filter(tenant=tenant_atual)

    stats = {
        "total_clientes": queryset.count(),
        "clientes_ativos": queryset.filter(status="active").count(),
        "clientes_pf": queryset.filter(tipo="PF").count(),
        "clientes_pj": queryset.filter(tipo="PJ").count(),
        "clientes_recentes": queryset.filter(data_cadastro__gte=datetime.now() - timedelta(days=30)).count(),
        "por_cidade": list(queryset.values("cidade").annotate(total=Count("id")).order_by("-total")[:10]),
        "por_status": list(queryset.values("status").annotate(total=Count("id")).order_by("status")),
    }

    return JsonResponse(stats)

# funcionarios/views_estoque.py
# Views para controle de materiais/estoque integrado com sistema existente

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView

from estoque.models import Deposito, MovimentoEstoque
from produtos.models import Produto

from .models import Funcionario
from .models_estoque import ItemSolicitacaoMaterial, ResponsabilidadeMaterial, SolicitacaoMaterial
from .services.estoque_service import EstoqueFuncionarioService


@login_required
def dashboard_materiais(request):
    """Dashboard integrado de materiais para funcionários"""

    # Estatísticas básicas
    funcionario_logado = getattr(request.user, "funcionario_profile", None)

    # Estatísticas de solicitações
    solicitacoes_stats = {
        "pendentes": SolicitacaoMaterial.objects.filter(tenant=request.user.tenant, status="pendente").count(),
        "aprovadas": SolicitacaoMaterial.objects.filter(tenant=request.user.tenant, status="aprovada").count(),
        "entregues_hoje": SolicitacaoMaterial.objects.filter(
            tenant=request.user.tenant, status="entregue", entregue_em__date=timezone.now().date()
        ).count(),
    }

    # Histórico recente usando sistema de estoque existente
    historico_recente = []
    if funcionario_logado:
        historico_recente = EstoqueFuncionarioService.get_historico_solicitacoes(funcionario_logado, limit=10)

    # Materiais sob responsabilidade
    materiais_responsabilidade = []
    if funcionario_logado:
        materiais_responsabilidade = EstoqueFuncionarioService.get_materiais_funcionario(funcionario_logado)[:5]

    context = {
        "stats": solicitacoes_stats,
        "historico_recente": historico_recente,
        "materiais_responsabilidade": materiais_responsabilidade,
        "funcionario": funcionario_logado,
        "title": "Dashboard de Materiais",
    }

    return render(request, "funcionarios/materiais/dashboard.html", context)


class SolicitacaoMaterialListView(LoginRequiredMixin, ListView):
    """Lista de solicitações de materiais"""

    model = SolicitacaoMaterial
    template_name = "funcionarios/solicitacoes/list.html"
    context_object_name = "solicitacoes"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            SolicitacaoMaterial.objects.filter(tenant=self.request.user.tenant)
            .select_related("funcionario_solicitante", "obra", "departamento", "aprovador")
            .prefetch_related("itens")
        )

        # Filtros
        status = self.request.GET.get("status")
        funcionario = self.request.GET.get("funcionario")
        tipo = self.request.GET.get("tipo")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if status:
            queryset = queryset.filter(status=status)

        if funcionario:
            queryset = queryset.filter(funcionario_solicitante_id=funcionario)

        if tipo:
            queryset = queryset.filter(tipo=tipo)

        if data_inicio:
            queryset = queryset.filter(data_solicitacao__date__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data_solicitacao__date__lte=data_fim)

        return queryset.order_by("-data_solicitacao")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Dados para filtros
        context["funcionarios"] = Funcionario.objects.filter(tenant=self.request.user.tenant, ativo=True).order_by(
            "nome_completo"
        )

        context["status_choices"] = SolicitacaoMaterial.STATUS_CHOICES
        context["tipo_choices"] = SolicitacaoMaterial.TIPO_CHOICES

        # Estatísticas rápidas
        context["stats"] = {
            "pendentes": SolicitacaoMaterial.objects.filter(
                tenant=self.request.user.tenant, status__in=["PENDENTE", "EM_ANALISE"]
            ).count(),
            "aprovadas": SolicitacaoMaterial.objects.filter(
                tenant=self.request.user.tenant, status__in=["APROVADA", "APROVADA_PARCIAL"]
            ).count(),
            "entregues_hoje": SolicitacaoMaterial.objects.filter(
                tenant=self.request.user.tenant, data_entrega__date=timezone.now().date()
            ).count(),
        }

        return context


class SolicitacaoMaterialDetailView(LoginRequiredMixin, DetailView):
    """Detalhes de uma solicitação de material"""

    model = SolicitacaoMaterial
    template_name = "funcionarios/solicitacoes/detail.html"
    context_object_name = "solicitacao"

    def get_queryset(self):
        return (
            SolicitacaoMaterial.objects.filter(tenant=self.request.user.tenant)
            .select_related("funcionario_solicitante", "obra", "departamento", "aprovador", "funcionario_entrega")
            .prefetch_related("itens__produto", "itens__deposito_origem")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estatísticas dos itens
        itens = self.object.itens.all()
        context["total_itens"] = itens.count()
        context["valor_total_estimado"] = sum(item.valor_total_estimado for item in itens)
        context["valor_total_real"] = sum(item.valor_total_real for item in itens)

        # Verificar se pode aprovar
        funcionario_logado = getattr(self.request.user, "funcionario_profile", None)
        context["pode_aprovar"] = (
            funcionario_logado
            and self.object.status in ["PENDENTE", "EM_ANALISE"]
            and (
                self.object.aprovador == funcionario_logado
                or funcionario_logado in self.object.funcionario_solicitante.funcionarios_supervisionados.all()
            )
        )

        return context


class SolicitacaoMaterialCreateView(LoginRequiredMixin, CreateView):
    """Criação de nova solicitação de material"""

    model = SolicitacaoMaterial
    template_name = "funcionarios/solicitacoes/create.html"
    fields = ["tipo", "prioridade", "obra", "departamento", "data_necessidade", "justificativa", "observacoes"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Filtrar obras e departamentos por tenant
        form.fields["obra"].queryset = form.fields["obra"].queryset.filter(tenant=self.request.user.tenant)
        form.fields["departamento"].queryset = form.fields["departamento"].queryset.filter(
            tenant=self.request.user.tenant
        )

        return form

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.funcionario_solicitante = self.request.user.funcionario_profile

        # Definir aprovador padrão se existir
        perfil_funcionario = getattr(self.request.user.funcionario_profile, "perfil_estoque", None)
        if perfil_funcionario and perfil_funcionario.aprovador:
            form.instance.aprovador = perfil_funcionario.aprovador

        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, _("Solicitação criada com sucesso! Agora adicione os itens necessários."))
        return reverse_lazy("funcionarios:solicitacao_add_item", kwargs={"pk": self.object.pk})


@login_required
def solicitacao_add_item(request, pk):
    """Adicionar item à solicitação"""
    solicitacao = get_object_or_404(SolicitacaoMaterial, pk=pk, tenant=request.user.tenant)

    if solicitacao.status not in ["RASCUNHO", "PENDENTE"]:
        messages.error(request, _("Não é possível adicionar itens a esta solicitação."))
        return redirect("funcionarios:solicitacao_detail", pk=pk)

    if request.method == "POST":
        produto_id = request.POST.get("produto")
        quantidade = request.POST.get("quantidade")
        deposito_id = request.POST.get("deposito")
        observacoes = request.POST.get("observacoes", "")
        urgente = request.POST.get("urgente") == "on"

        try:
            produto = Produto.objects.get(id=produto_id)
            deposito = Deposito.objects.get(id=deposito_id, tenant=request.user.tenant)

            # Verificar se o item já existe
            item_existente = ItemSolicitacaoMaterial.objects.filter(
                solicitacao=solicitacao, produto=produto, deposito_origem=deposito
            ).first()

            if item_existente:
                # Atualizar quantidade
                item_existente.quantidade_solicitada += float(quantidade)
                item_existente.save()
                messages.success(request, _("Quantidade do item atualizada."))
            else:
                # Criar novo item
                ItemSolicitacaoMaterial.objects.create(
                    solicitacao=solicitacao,
                    produto=produto,
                    quantidade_solicitada=quantidade,
                    deposito_origem=deposito,
                    custo_unitario_estimado=produto.preco_custo,
                    observacoes_item=observacoes,
                    urgente=urgente,
                )
                messages.success(request, _("Item adicionado à solicitação."))

            # Atualizar valor total estimado da solicitação
            solicitacao.valor_total_estimado = sum(item.valor_total_estimado for item in solicitacao.itens.all())
            solicitacao.save()

        except (Produto.DoesNotExist, Deposito.DoesNotExist, ValueError):
            messages.error(request, _("Erro ao adicionar item. Verifique os dados."))

    context = {
        "solicitacao": solicitacao,
        "produtos": Produto.objects.filter(ativo=True).order_by("nome"),
        "depositos": Deposito.objects.filter(tenant=request.user.tenant, ativo=True).order_by("nome"),
    }

    return render(request, "funcionarios/solicitacoes/add_item.html", context)


@login_required
def aprovar_solicitacao(request, pk):
    """Aprovar ou rejeitar uma solicitação"""
    solicitacao = get_object_or_404(SolicitacaoMaterial, pk=pk, tenant=request.user.tenant)

    funcionario_logado = getattr(request.user, "funcionario_profile", None)

    # Verificar permissão de aprovação
    pode_aprovar = (
        funcionario_logado
        and solicitacao.status in ["PENDENTE", "EM_ANALISE"]
        and (
            solicitacao.aprovador == funcionario_logado
            or funcionario_logado in solicitacao.funcionario_solicitante.funcionarios_supervisionados.all()
        )
    )

    if not pode_aprovar:
        messages.error(request, _("Você não tem permissão para aprovar esta solicitação."))
        return redirect("funcionarios:solicitacao_detail", pk=pk)

    if request.method == "POST":
        acao = request.POST.get("acao")  # 'aprovar' ou 'rejeitar'
        observacoes = request.POST.get("observacoes", "")

        try:
            if acao == "aprovar":
                EstoqueFuncionarioService.aprovar_solicitacao(
                    solicitacao=solicitacao, aprovador=funcionario_logado, aprovado=True
                )
                messages.success(request, _("Solicitação aprovada com sucesso."))

            elif acao == "rejeitar":
                EstoqueFuncionarioService.aprovar_solicitacao(
                    solicitacao=solicitacao, aprovador=funcionario_logado, aprovado=False, motivo_rejeicao=observacoes
                )
                messages.success(request, _("Solicitação rejeitada."))
        except Exception as e:
            messages.error(request, f"Erro ao processar solicitação: {str(e)}")

            solicitacao.save()

    return redirect("funcionarios:solicitacao_detail", pk=pk)


@login_required
def entregar_material(request, pk):
    """Interface para entrega de materiais"""
    solicitacao = get_object_or_404(SolicitacaoMaterial, pk=pk, tenant=request.user.tenant, status="APROVADA")

    if request.method == "POST":
        try:
            itens_entregues = []

            for item in solicitacao.itens.all():
                quantidade_entregue = request.POST.get(f"quantidade_{item.id}")

                if quantidade_entregue and float(quantidade_entregue) > 0:
                    itens_entregues.append({"item_id": item.id, "quantidade": float(quantidade_entregue)})

            if itens_entregues:
                EstoqueFuncionarioService.entregar_material(
                    solicitacao=solicitacao, entregador=request.user, itens_entregues=itens_entregues
                )
                messages.success(request, _("Materiais entregues com sucesso."))
            else:
                messages.warning(request, _("Nenhum item foi selecionado para entrega."))

        except Exception as e:
            messages.error(request, f"Erro na entrega: {str(e)}")

        return redirect("funcionarios:solicitacao_detail", pk=pk)

    context = {
        "solicitacao": solicitacao,
    }

    return render(request, "funcionarios/solicitacoes/entregar.html", context)


@login_required
def retirada_rapida(request):
    """Interface para retirada rápida de materiais (manual)"""

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Dados do formulário
                funcionario_id = request.POST.get("funcionario")
                deposito_id = request.POST.get("deposito")
                produtos_ids = request.POST.getlist("produtos[]")
                quantidades = request.POST.getlist("quantidades[]")
                motivo = request.POST.get("motivo")
                observacoes = request.POST.get("observacoes", "")
                data_previsao = request.POST.get("data_previsao_devolucao")

                # Validações
                funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=request.user.tenant)
                deposito = get_object_or_404(Deposito, id=deposito_id, tenant=request.user.tenant)

                # Criar solicitação automática
                solicitacao = SolicitacaoMaterial.objects.create(
                    funcionario=funcionario,
                    tenant=request.user.tenant,
                    motivo=f"Retirada manual - {motivo}",
                    observacao=observacoes,
                    status="ENTREGUE",  # Já entregue diretamente
                    tipo="MANUAL",
                    data_entrega=timezone.now(),
                    solicitante_user=request.user,
                )

                # Processar itens
                for i, produto_id in enumerate(produtos_ids):
                    if produto_id and i < len(quantidades):
                        produto = get_object_or_404(Produto, id=produto_id)
                        quantidade = float(quantidades[i])

                        # Criar item da solicitação
                        ItemSolicitacaoMaterial.objects.create(
                            solicitacao=solicitacao,
                            produto=produto,
                            quantidade_solicitada=quantidade,
                            quantidade_entregue=quantidade,
                            data_entrega=timezone.now(),
                            tenant=request.user.tenant,
                        )

                        # Criar movimento de estoque
                        movimento = MovimentoEstoque.objects.create(
                            produto=produto,
                            tenant=request.user.tenant,
                            deposito_origem=deposito,
                            tipo="SAIDA",
                            quantidade=quantidade,
                            usuario_executante=request.user,
                            solicitante_tipo="funcionario",
                            solicitante_id=str(funcionario.id),
                            solicitante_nome_cache=funcionario.nome_completo,
                            motivo=f"Retirada manual - {motivo}",
                            ref_externa=f"MAN-{solicitacao.numero}",
                        )

                        # Criar responsabilidade se necessário
                        if motivo not in ["consumo_imediato"]:
                            data_prev_devolucao = None
                            if data_previsao:
                                from django.utils.dateparse import parse_date

                                data_prev_devolucao = parse_date(data_previsao)

                            ResponsabilidadeMaterial.objects.create(
                                funcionario=funcionario,
                                produto=produto,
                                quantidade=quantidade,
                                data_retirada=timezone.now(),
                                data_previsao_devolucao=data_prev_devolucao,
                                movimento_estoque=movimento,
                                tenant=request.user.tenant,
                                status="ATIVO",
                                tipo_responsabilidade=motivo,
                            )

                messages.success(request, f"Retirada realizada com sucesso! {len(produtos_ids)} item(ns) entregue(s).")
                return redirect("funcionarios_estoque:dashboard_materiais")

        except Exception as e:
            messages.error(request, f"Erro na retirada: {str(e)}")

    # Dados para o template
    context = {
        "funcionarios": Funcionario.objects.filter(tenant=request.user.tenant, ativo=True).order_by("nome_completo"),
        "depositos": Deposito.objects.filter(tenant=request.user.tenant, ativo=True),
        "produtos": Produto.objects.filter(tenant=request.user.tenant, ativo=True).order_by("nome"),
        "retiradas_recentes": SolicitacaoMaterial.objects.filter(
            tenant=request.user.tenant, tipo="MANUAL", status="ENTREGUE"
        ).order_by("-data_entrega")[:5],
        "stats": {
            "retiradas_hoje": SolicitacaoMaterial.objects.filter(
                tenant=request.user.tenant, tipo="MANUAL", data_entrega__date=timezone.now().date()
            ).count(),
            "devolucoes_hoje": ResponsabilidadeMaterial.objects.filter(
                tenant=request.user.tenant, data_devolucao__date=timezone.now().date()
            ).count(),
        },
    }

    return render(request, "funcionarios/materiais/retirada_rapida.html", context)


@login_required
def devolucao_material(request):
    """Interface para devolução de materiais"""

    if request.method == "POST":
        try:
            with transaction.atomic():
                funcionario_id = request.POST.get("funcionario")
                materiais_ids = request.POST.getlist("materiais_devolver[]")
                quantidades = request.POST.getlist("quantidades_devolver[]")
                motivo = request.POST.get("motivo_devolucao")
                deposito_id = request.POST.get("deposito_destino")
                observacoes = request.POST.get("observacoes", "")

                funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=request.user.tenant)
                deposito = get_object_or_404(Deposito, id=deposito_id, tenant=request.user.tenant)

                devolucoes_realizadas = 0

                for i, responsabilidade_id in enumerate(materiais_ids):
                    if responsabilidade_id and i < len(quantidades):
                        responsabilidade = get_object_or_404(
                            ResponsabilidadeMaterial, id=responsabilidade_id, funcionario=funcionario, status="ATIVO"
                        )

                        quantidade_devolver = float(quantidades[i])

                        if quantidade_devolver > responsabilidade.quantidade:
                            raise ValueError(
                                f"Quantidade de devolução maior que a em posse para {responsabilidade.produto.nome}"
                            )

                        # Criar movimento de entrada (devolução)
                        MovimentoEstoque.objects.create(
                            produto=responsabilidade.produto,
                            tenant=request.user.tenant,
                            deposito_destino=deposito,
                            tipo="DEVOLUCAO_FUNCIONARIO",
                            quantidade=quantidade_devolver,
                            usuario_executante=request.user,
                            solicitante_tipo="funcionario",
                            solicitante_id=str(funcionario.id),
                            solicitante_nome_cache=funcionario.nome_completo,
                            motivo=f"Devolução manual - {motivo}",
                            metadata={
                                "responsabilidade_id": responsabilidade.id,
                                "motivo_devolucao": motivo,
                                "observacoes": observacoes,
                            },
                        )

                        # Atualizar responsabilidade
                        responsabilidade.quantidade -= quantidade_devolver
                        if responsabilidade.quantidade == 0:
                            responsabilidade.status = "DEVOLVIDO"
                            responsabilidade.data_devolucao = timezone.now()
                        responsabilidade.motivo_devolucao = motivo
                        responsabilidade.observacoes_devolucao = observacoes
                        responsabilidade.save()

                        devolucoes_realizadas += 1

                messages.success(
                    request, f"Devolução realizada com sucesso! {devolucoes_realizadas} item(ns) devolvido(s)."
                )
                return redirect("funcionarios_estoque:dashboard_materiais")

        except Exception as e:
            messages.error(request, f"Erro na devolução: {str(e)}")

    # Dados para o template
    funcionarios_com_resp = (
        Funcionario.objects.filter(tenant=request.user.tenant, ativo=True, responsabilidades_material__status="ATIVO")
        .distinct()
        .order_by("nome_completo")
    )

    context = {
        "funcionarios_com_responsabilidade": funcionarios_com_resp,
        "depositos": Deposito.objects.filter(tenant=request.user.tenant, ativo=True),
        "devolucoes_recentes": ResponsabilidadeMaterial.objects.filter(
            tenant=request.user.tenant, status="DEVOLVIDO"
        ).order_by("-data_devolucao")[:5],
        "materiais_em_atraso": ResponsabilidadeMaterial.objects.filter(
            tenant=request.user.tenant, status="ATIVO", data_previsao_devolucao__lt=timezone.now().date()
        ).order_by("data_previsao_devolucao")[:5],
    }

    return render(request, "funcionarios/materiais/devolucao.html", context)


@login_required
def ajax_responsabilidades_funcionario(request, funcionario_id):
    """Retorna responsabilidades ativas de um funcionário via AJAX"""
    try:
        funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=request.user.tenant)

        responsabilidades = ResponsabilidadeMaterial.objects.filter(
            funcionario=funcionario, status="ATIVO"
        ).select_related("produto")

        data = {"responsabilidades": []}

        for resp in responsabilidades:
            dias_posse = (timezone.now().date() - resp.data_retirada.date()).days

            data["responsabilidades"].append(
                {
                    "id": resp.id,
                    "produto": {
                        "nome": resp.produto.nome,
                        "codigo": resp.produto.codigo,
                        "unidade": getattr(resp.produto.unidade, "codigo", "UN") if resp.produto.unidade else "UN",
                    },
                    "quantidade": str(resp.quantidade),
                    "data_retirada_formatada": resp.data_retirada.strftime("%d/%m/%Y"),
                    "dias_posse": dias_posse,
                    "status": resp.status,
                }
            )

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


class ResponsabilidadeMaterialListView(LoginRequiredMixin, ListView):
    """Lista de materiais sob responsabilidade"""

    model = ResponsabilidadeMaterial
    template_name = "funcionarios/responsabilidades/list.html"
    context_object_name = "responsabilidades"
    paginate_by = 20

    def get_queryset(self):
        queryset = ResponsabilidadeMaterial.objects.select_related("funcionario", "produto", "obra")

        # Filtro por funcionário se especificado
        funcionario_id = self.request.GET.get("funcionario")
        if funcionario_id:
            queryset = queryset.filter(funcionario_id=funcionario_id)

        # Filtro por status
        status = self.request.GET.get("status", "ATIVO")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-data_retirada")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["funcionarios"] = Funcionario.objects.filter(tenant=self.request.user.tenant, ativo=True).order_by(
            "nome_completo"
        )

        context["status_choices"] = ResponsabilidadeMaterial.STATUS_CHOICES

        # Estatísticas
        context["stats"] = {
            "total_ativo": ResponsabilidadeMaterial.objects.filter(
                funcionario__tenant=self.request.user.tenant, status="ATIVO"
            ).count(),
            "em_atraso": ResponsabilidadeMaterial.objects.filter(
                funcionario__tenant=self.request.user.tenant,
                status="ATIVO",
                data_previsao_devolucao__lt=timezone.now().date(),
            ).count(),
            "valor_total": ResponsabilidadeMaterial.objects.filter(
                funcionario__tenant=self.request.user.tenant, status="ATIVO"
            ).aggregate(total=Sum("valor_unitario"))["total"]
            or 0,
        }

        return context


# Views para API/AJAX
@login_required
def produtos_por_categoria(request):
    """Retorna produtos filtrados por categoria (AJAX)"""
    categoria_id = request.GET.get("categoria_id")

    produtos = Produto.objects.filter(ativo=True)
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)

    data = [
        {
            "id": produto.id,
            "nome": produto.nome,
            "preco_custo": float(produto.preco_custo),
            "estoque_atual": produto.estoque_atual,
        }
        for produto in produtos.order_by("nome")[:50]  # Limit para performance
    ]

    return JsonResponse({"produtos": data})

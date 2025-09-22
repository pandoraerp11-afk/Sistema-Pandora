"""Views do módulo estoque incluindo controle de materiais para funcionários.
Novas views modernas serão adicionadas conforme plano de frontend (versão 3.0).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from core.utils import get_current_tenant
from funcionarios.models import Funcionario
from funcionarios.models_estoque import ResponsabilidadeMaterial, SolicitacaoMaterial
from funcionarios.services.estoque_service import EstoqueFuncionarioService
from produtos.models import Produto
from shared.mixins.ui_permissions import UIPermissionsMixin
from shared.services.ui_permissions import build_ui_permissions

from .models import Deposito, EstoqueSaldo, MovimentoEstoque


def placeholder(request):
    return HttpResponse(
        "Modulo estoque modernizado – Views web clássicas removidas. Use APIs / novas telas em desenvolvimento."
    )


@login_required
def estoque_home(request):
    """
    View principal do módulo estoque - renderiza estoque_home.html
    """
    # Obter tenant de forma segura usando função utilitária
    tenant = get_current_tenant(request)

    # Estatísticas básicas do estoque
    stats = {
        "total_produtos": 0,  # Implementar busca real
        "produtos_ativos": 0,
        "valor_total_estoque": 0,
        "produtos_baixo_estoque": 0,
        "total_reservado": 0,
        "reservas_ativas": 0,
    }

    # Estatísticas de materiais para funcionários (apenas se tenant existir)
    if tenant:
        try:
            from django.utils import timezone

            stats.update(
                {
                    "materiais_funcionarios": ResponsabilidadeMaterial.objects.filter(
                        funcionario__tenant=tenant, status="ATIVO"
                    ).count(),
                    "funcionarios_com_material": ResponsabilidadeMaterial.objects.filter(
                        funcionario__tenant=tenant, status="ATIVO"
                    )
                    .values("funcionario")
                    .distinct()
                    .count(),
                    "materiais_em_atraso": ResponsabilidadeMaterial.objects.filter(
                        funcionario__tenant=tenant, status="ATIVO", data_previsao_devolucao__lt=timezone.now().date()
                    ).count(),
                    "retiradas_hoje": MovimentoEstoque.objects.filter(
                        tenant=tenant,
                        tipo="SAIDA",
                        data_movimento__date=timezone.now().date(),
                        solicitante_tipo__icontains="funcionario",
                    ).count(),
                    "devolucoes_hoje": MovimentoEstoque.objects.filter(
                        tenant=tenant, tipo="DEVOLUCAO_FUNCIONARIO", data_movimento__date=timezone.now().date()
                    ).count(),
                    "valor_materiais_funcionarios": ResponsabilidadeMaterial.objects.filter(
                        funcionario__tenant=tenant, status="ATIVO"
                    ).aggregate(total=Sum("valor_unitario"))["total"]
                    or 0,
                }
            )
        except Exception as e:
            # Se houver qualquer erro, usar valores padrão e log do erro
            print(f"Erro ao carregar estatísticas de materiais: {e}")
            stats.update(
                {
                    "materiais_funcionarios": 0,
                    "funcionarios_com_material": 0,
                    "materiais_em_atraso": 0,
                    "retiradas_hoje": 0,
                    "devolucoes_hoje": 0,
                    "valor_materiais_funcionarios": 0,
                }
            )
    else:
        # Se não há tenant, usar valores padrão
        stats.update(
            {
                "materiais_funcionarios": 0,
                "funcionarios_com_material": 0,
                "materiais_em_atraso": 0,
                "retiradas_hoje": 0,
                "devolucoes_hoje": 0,
                "valor_materiais_funcionarios": 0,
            }
        )

    # Alertas e pendências
    alertas = {
        "produtos_zerados": 0,
        "reservas_expirando": 0,
        "pedidos_pendentes": 0,
        "produtos_baixo_estoque": 0,
    }

    # Dados para gráfico (estrutura básica)
    grafico_movimentacao = {
        "labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        "entradas": [10, 15, 8, 20, 12, 5, 3],
        "saidas": [8, 12, 10, 18, 15, 7, 2],
    }

    ui_perms = build_ui_permissions(request.user, tenant, app_label="estoque", model_name="estoquesaldo")

    context = {
        "title": "Estoque - Controle e Gestão",
        "module_name": "estoque",
        "stats": stats,
        "alertas": alertas,
        "grafico_movimentacao": grafico_movimentacao,
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, "estoque/estoque_home.html", context)


# =============================
# CONTROLE DE MATERIAIS PARA FUNCIONÁRIOS
# =============================


@login_required
def controle_materiais_funcionarios(request):
    """Dashboard de controle de materiais para funcionários"""
    tenant = get_current_tenant(request)

    # Se não há tenant, retornar dados vazios
    if not tenant:
        stats = {
            "solicitacoes_pendentes": 0,
            "solicitacoes_mes": 0,
            "materiais_responsabilidade": 0,
            "materiais_em_atraso": 0,
        }
    else:
        # Estatísticas gerais
        try:
            stats = {
                "solicitacoes_pendentes": SolicitacaoMaterial.objects.filter(
                    tenant=tenant, status__in=["PENDENTE", "EM_ANALISE"]
                ).count(),
                "solicitacoes_mes": SolicitacaoMaterial.objects.filter(
                    tenant=tenant,
                    data_solicitacao__month=timezone.now().month,
                    data_solicitacao__year=timezone.now().year,
                ).count(),
                "materiais_responsabilidade": ResponsabilidadeMaterial.objects.filter(
                    funcionario__tenant=tenant, status="ATIVO"
                ).count(),
                "materiais_em_atraso": ResponsabilidadeMaterial.objects.filter(
                    funcionario__tenant=tenant, status="ATIVO", data_previsao_devolucao__lt=timezone.now().date()
                ).count(),
            }
        except Exception as e:
            # Em caso de erro, usar valores padrão
            print(f"Erro ao carregar estatísticas: {e}")
            stats = {
                "solicitacoes_pendentes": 0,
                "solicitacoes_mes": 0,
                "materiais_responsabilidade": 0,
                "materiais_em_atraso": 0,
            }

    context = {"stats": stats, "title": "Controle de Materiais - Funcionários", "module_name": "estoque"}

    return render(request, "estoque/controle_materiais_funcionarios.html", context)


@login_required
def retirada_rapida_material(request):
    """Interface para retirada rápida de materiais por funcionários"""
    if request.method == "POST":
        try:
            with transaction.atomic():
                tenant = get_current_tenant(request)
                funcionario_id = request.POST.get("funcionario_id")
                deposito_id = request.POST.get("deposito_id")
                motivo = request.POST.get("motivo", "USO_OBRA")

                funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=tenant)

                deposito = get_object_or_404(Deposito, id=deposito_id, tenant=tenant)  # Processar itens selecionados
                produtos_ids = request.POST.getlist("produto_id")
                quantidades = request.POST.getlist("quantidade")

                service = EstoqueFuncionarioService()

                for produto_id, quantidade in zip(produtos_ids, quantidades, strict=False):
                    if produto_id and quantidade:
                        produto = get_object_or_404(Produto, id=produto_id)

                        # Criar movimento de saída diretamente
                        service.criar_movimento_saida(
                            funcionario=funcionario,
                            produto=produto,
                            quantidade=float(quantidade),
                            deposito=deposito,
                            motivo=motivo,
                            usuario_sistema=request.user,
                        )

                messages.success(request, "Materiais retirados com sucesso!")
                return redirect("estoque:retirada_rapida_material")

        except Exception as e:
            messages.error(request, f"Erro ao processar retirada: {str(e)}")

    # GET - mostrar formulário
    tenant = get_current_tenant(request)
    funcionarios = Funcionario.objects.filter(tenant=tenant, ativo=True).order_by("nome")

    depositos = Deposito.objects.filter(tenant=tenant).order_by("nome")

    context = {
        "funcionarios": funcionarios,
        "depositos": depositos,
        "title": "Retirada Rápida de Material",
        "module_name": "estoque",
    }

    return render(request, "estoque/retirada_rapida_material.html", context)


@login_required
def devolucao_material_funcionario(request):
    """Interface para devolução de materiais por funcionários"""
    if request.method == "POST":
        try:
            with transaction.atomic():
                tenant = get_current_tenant(request)
                funcionario_id = request.POST.get("funcionario_id")
                motivo = request.POST.get("motivo", "TRABALHO_CONCLUIDO")

                funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=tenant)

                # Processar devoluções
                responsabilidade_ids = request.POST.getlist("responsabilidade_id")
                quantidades_devolucao = request.POST.getlist("quantidade_devolucao")

                service = EstoqueFuncionarioService()

                for resp_id, quantidade in zip(responsabilidade_ids, quantidades_devolucao, strict=False):
                    if resp_id and quantidade:
                        responsabilidade = get_object_or_404(
                            ResponsabilidadeMaterial, id=resp_id, funcionario=funcionario
                        )

                        service.processar_devolucao(
                            responsabilidade=responsabilidade,
                            quantidade_devolvida=float(quantidade),
                            motivo=motivo,
                            usuario_sistema=request.user,
                        )

                messages.success(request, "Materiais devolvidos com sucesso!")
                return redirect("estoque:devolucao_material_funcionario")

        except Exception as e:
            messages.error(request, f"Erro ao processar devolução: {str(e)}")

    # GET - mostrar formulário
    tenant = get_current_tenant(request)
    funcionarios = Funcionario.objects.filter(tenant=tenant, ativo=True).order_by("nome")

    context = {"funcionarios": funcionarios, "title": "Devolução de Material", "module_name": "estoque"}

    return render(request, "estoque/devolucao_material_funcionario.html", context)


@login_required
def ajax_responsabilidades_funcionario(request, funcionario_id):
    """API para carregar responsabilidades de material de um funcionário"""
    try:
        tenant = get_current_tenant(request)
        funcionario = get_object_or_404(Funcionario, id=funcionario_id, tenant=tenant)

        responsabilidades = ResponsabilidadeMaterial.objects.filter(
            funcionario=funcionario, status="ATIVO"
        ).select_related("produto")

        data = [
            {
                "id": resp.id,
                "produto_nome": resp.produto.nome,
                "quantidade_atual": float(resp.quantidade_atual),
                "valor_unitario": float(resp.valor_unitario),
                "data_previsao": resp.data_previsao_devolucao.strftime("%d/%m/%Y")
                if resp.data_previsao_devolucao
                else "",
                "em_atraso": resp.data_previsao_devolucao < timezone.now().date()
                if resp.data_previsao_devolucao
                else False,
            }
            for resp in responsabilidades
        ]

        return JsonResponse({"responsabilidades": data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# =============================
# Placeholders para rotas usadas nos templates
# =============================


@login_required
def saldos_list(request):
    return render(request, "estoque/saldos_list.html", {})


@login_required
def movimentos_list(request):
    return render(request, "estoque/movimentos/list_placeholder.html", {})


@login_required
def reservas_list(request):
    return render(request, "estoque/reservas_list.html", {})


@login_required
def picking_list(request):
    return render(request, "estoque/picking_list.html", {})


@login_required
def picking_kanban(request):
    return render(request, "estoque/picking/kanban.html", {})


@login_required
def auditoria_list(request):
    return render(request, "estoque/auditoria/list_placeholder.html", {})


@login_required
def depositos_list(request):
    return render(request, "estoque/depositos/list_placeholder.html", {})


@login_required
def movimento_add(request):
    return HttpResponse("Form de nova movimentação (placeholder).")


@login_required
def reserva_add(request):
    return HttpResponse("Form de nova reserva (placeholder).")


# =============================
# Views modernas provisórias para Itens de Estoque
# =============================


class EstoqueItemListView(UIPermissionsMixin, ListView):
    model = EstoqueSaldo
    template_name = "estoque/estoque_list.html"
    context_object_name = "itens_estoque"
    paginate_by = 25
    app_label = "estoque"
    model_name = "estoquesaldo"

    def get_queryset(self):
        qs = super().get_queryset().select_related("produto", "deposito")
        produto = self.request.GET.get("produto")
        if produto:
            qs = qs.filter(produto__nome__icontains=produto)
        categoria = self.request.GET.get("categoria")
        if categoria:
            qs = qs.filter(produto__categoria_id=categoria)
        # Ordenação explícita para paginação consistente
        qs = qs.order_by("id")
        # guarda queryset completo para métricas
        self._full_queryset = qs
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        full_qs = getattr(self, "_full_queryset", None) or self.get_queryset()
        ctx["estoque_critico"] = full_qs.filter(quantidade__lte=0).count()
        ctx["estoque_baixo"] = full_qs.filter(quantidade__gt=0, quantidade__lte=10).count()
        ctx["estoque_normal"] = full_qs.filter(quantidade__gt=10).count()
        ctx.setdefault("page_title", "Controle de Estoque")
        ctx.setdefault("page_subtitle", "Gerencie itens e níveis (fase de modernização)")
        return ctx


class EstoqueItemDetailView(UIPermissionsMixin, DetailView):
    model = EstoqueSaldo
    template_name = "estoque/estoque_detail.html"
    context_object_name = "itemestoque"
    app_label = "estoque"
    model_name = "estoquesaldo"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

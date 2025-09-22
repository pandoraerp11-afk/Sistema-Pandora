# funcionarios/services/estoque_service.py
# Service Layer para integração inteligente funcionários-estoque

import builtins
import contextlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from estoque.models import MovimentoEstoque
from notifications.models import Notification

from ..models_estoque import ItemSolicitacaoMaterial, ResponsabilidadeMaterial, SolicitacaoMaterial


class EstoqueFuncionarioService:
    """Service para operações de estoque relacionadas a funcionários"""

    @staticmethod
    def solicitar_material(funcionario, itens_solicitacao, deposito, motivo="", observacao=""):
        """Cria solicitação de material aproveitando o sistema de MovimentoEstoque existente

        Args:
            funcionario: Instância do funcionário
            itens_solicitacao: Lista de dicts {'produto': produto, 'quantidade': qtd}
            deposito: Deposito de origem
            motivo: Motivo da solicitação
            observacao: Observações adicionais

        Returns:
            SolicitacaoMaterial criada

        """
        with transaction.atomic():
            # 1. Criar solicitação no sistema específico
            solicitacao = SolicitacaoMaterial.objects.create(
                funcionario=funcionario,
                tenant=funcionario.tenant,
                deposito=deposito,
                motivo=motivo,
                observacao=observacao,
                status="PENDENTE",
            )

            # 2. Criar itens da solicitação
            total_valor = Decimal("0")
            for item_data in itens_solicitacao:
                produto = item_data["produto"]
                quantidade = item_data["quantidade"]

                ItemSolicitacaoMaterial.objects.create(
                    solicitacao=solicitacao,
                    produto=produto,
                    quantidade_solicitada=quantidade,
                    tenant=funcionario.tenant,
                )

                # Calcular valor estimado
                if hasattr(produto, "custo_atual"):
                    total_valor += produto.custo_atual * quantidade

            # 3. Atualizar valor total da solicitação
            solicitacao.valor_total_estimado = total_valor
            solicitacao.save()

            # 4. Verificar se precisa de aprovação
            perfil = getattr(funcionario, "perfil_estoque", None)
            if perfil and perfil.necessita_aprovacao:
                solicitacao.status = "AGUARDANDO_APROVACAO"
                solicitacao.save()

                # Enviar notificação para aprovador
                if perfil.aprovador:
                    EstoqueFuncionarioService._enviar_notificacao_aprovacao(solicitacao, perfil.aprovador)

            return solicitacao

    @staticmethod
    def aprovar_solicitacao(solicitacao, aprovador, aprovado=True, motivo_rejeicao=""):
        """Aprova ou rejeita uma solicitação"""
        with transaction.atomic():
            if aprovado:
                solicitacao.status = "APROVADA"
                solicitacao.aprovado_por = aprovador
                solicitacao.aprovado_em = timezone.now()

                # Criar movimento de reserva no estoque
                for item in solicitacao.itens.all():
                    MovimentoEstoque.objects.create(
                        produto=item.produto,
                        tenant=solicitacao.tenant,
                        deposito_origem=solicitacao.deposito,
                        tipo="RESERVA",
                        quantidade=item.quantidade_solicitada,
                        usuario_executante=aprovador.user if hasattr(aprovador, "user") else None,
                        solicitante_tipo="funcionario",
                        solicitante_id=str(solicitacao.funcionario.id),
                        solicitante_nome_cache=solicitacao.funcionario.nome_completo,
                        motivo=f"Reserva para funcionário - {solicitacao.motivo}",
                        ref_externa=f"SOL-{solicitacao.numero}",
                    )
            else:
                solicitacao.status = "REJEITADA"
                solicitacao.motivo_rejeicao = motivo_rejeicao
                solicitacao.rejeitado_por = aprovador
                solicitacao.rejeitado_em = timezone.now()

            solicitacao.save()

            # Notificar funcionário
            EstoqueFuncionarioService._enviar_notificacao_status(solicitacao, aprovado)

    @staticmethod
    def entregar_material(solicitacao, entregador, itens_entregues):
        """Efetiva a entrega do material criando movimentos de saída no estoque

        Args:
            solicitacao: SolicitacaoMaterial
            entregador: Usuário que está fazendo a entrega
            itens_entregues: Lista de dicts {'item_id': id, 'quantidade': qtd}

        """
        with transaction.atomic():
            for item_data in itens_entregues:
                item = ItemSolicitacaoMaterial.objects.get(id=item_data["item_id"])
                quantidade_entregue = item_data["quantidade"]

                # Criar movimento de saída no estoque
                movimento = MovimentoEstoque.objects.create(
                    produto=item.produto,
                    tenant=solicitacao.tenant,
                    deposito_origem=solicitacao.deposito,
                    tipo="SAIDA",
                    quantidade=quantidade_entregue,
                    usuario_executante=entregador,
                    solicitante_tipo="funcionario",
                    solicitante_id=str(solicitacao.funcionario.id),
                    solicitante_nome_cache=solicitacao.funcionario.nome_completo,
                    motivo=f"Entrega de material para funcionário - {solicitacao.motivo}",
                    ref_externa=f"SOL-{solicitacao.numero}",
                )

                # Criar responsabilidade do material
                ResponsabilidadeMaterial.objects.create(
                    funcionario=solicitacao.funcionario,
                    produto=item.produto,
                    quantidade=quantidade_entregue,
                    data_retirada=timezone.now(),
                    movimento_estoque=movimento,
                    tenant=solicitacao.tenant,
                    status="ATIVO",
                )

                # Atualizar item
                item.quantidade_entregue = quantidade_entregue
                item.data_entrega = timezone.now()
                item.entregue_por = entregador
                item.save()

            # Verificar se todos os itens foram entregues
            total_itens = solicitacao.itens.count()
            itens_entregues = solicitacao.itens.filter(quantidade_entregue__gt=0).count()

            if total_itens == itens_entregues:
                solicitacao.status = "ENTREGUE"
                solicitacao.data_entrega = timezone.now()
                solicitacao.save()

                # Notificar conclusão
                EstoqueFuncionarioService._enviar_notificacao_entrega(solicitacao)

    @staticmethod
    def devolver_material(funcionario, produto, quantidade, motivo=""):
        """Registra devolução de material"""
        with transaction.atomic():
            # Encontrar responsabilidade ativa
            responsabilidade = ResponsabilidadeMaterial.objects.filter(
                funcionario=funcionario,
                produto=produto,
                status="ATIVO",
            ).first()

            if not responsabilidade:
                raise ValueError("Funcionário não possui responsabilidade ativa sobre este material")

            if responsabilidade.quantidade < quantidade:
                raise ValueError("Quantidade de devolução maior que a quantidade em posse")

            # Criar movimento de entrada (devolução)
            MovimentoEstoque.objects.create(
                produto=produto,
                tenant=funcionario.tenant,
                deposito_destino=responsabilidade.movimento_estoque.deposito_origem,
                tipo="DEVOLUCAO_FUNCIONARIO",
                quantidade=quantidade,
                solicitante_tipo="funcionario",
                solicitante_id=str(funcionario.id),
                solicitante_nome_cache=funcionario.nome_completo,
                motivo=f"Devolução de material - {motivo}",
            )

            # Atualizar responsabilidade
            responsabilidade.quantidade -= quantidade
            if responsabilidade.quantidade == 0:
                responsabilidade.status = "DEVOLVIDO"
                responsabilidade.data_devolucao = timezone.now()
            responsabilidade.save()

    @staticmethod
    def _enviar_notificacao_aprovacao(solicitacao, aprovador):
        """Envia notificação para aprovador"""
        if hasattr(aprovador, "user"):
            try:
                Notification.objects.create(
                    user=aprovador.user,
                    title=f"Aprovação de Material - {solicitacao.funcionario.nome_completo}",
                    message=f"Solicitação #{solicitacao.numero} aguardando sua aprovação",
                    notification_type="material_approval",
                )
            except Exception:
                pass  # Se não conseguir enviar notificação, continua

    @staticmethod
    def _enviar_notificacao_status(solicitacao, aprovado):
        """Envia notificação de status da solicitação"""
        if hasattr(solicitacao.funcionario, "user"):
            try:
                status = "aprovada" if aprovado else "rejeitada"
                Notification.objects.create(
                    user=solicitacao.funcionario.user,
                    title=f"Solicitação de Material {status.title()}",
                    message=f"Sua solicitação #{solicitacao.numero} foi {status}",
                    notification_type="material_status",
                )
            except Exception:
                pass

    @staticmethod
    def _enviar_notificacao_entrega(solicitacao):
        """Envia notificação de entrega concluída"""
        if hasattr(solicitacao.funcionario, "user"):
            with contextlib.suppress(builtins.BaseException):
                Notification.objects.create(
                    user=solicitacao.funcionario.user,
                    title="Material Entregue",
                    message=f"Solicitação #{solicitacao.numero} foi entregue com sucesso",
                    notification_type="material_delivery",
                )

    @staticmethod
    def get_materiais_funcionario(funcionario):
        """Retorna todos os materiais sob responsabilidade do funcionário"""
        return ResponsabilidadeMaterial.objects.filter(funcionario=funcionario, status="ATIVO").select_related(
            "produto",
        )

    @staticmethod
    def get_historico_solicitacoes(funcionario, limit=10):
        """Retorna histórico de solicitações do funcionário"""
        return SolicitacaoMaterial.objects.filter(funcionario=funcionario).order_by("-criado_em")[:limit]

# funcionarios/services/estoque.py
# Service Layer para integração inteligente com sistema de estoque existente

from django.db import transaction
from django.utils import timezone

from estoque.models import Deposito, EstoqueSaldo, MovimentoEstoque

from ..models import Funcionario
from ..models_estoque import ItemSolicitacaoMaterial, ResponsabilidadeMaterial, SolicitacaoMaterial


class EstoqueIntegrationService:
    """
    Service para integrar solicitações de funcionários com sistema de estoque existente
    Aproveita a infraestrutura de MovimentoEstoque já implementada
    """

    @staticmethod
    @transaction.atomic
    def solicitar_material(funcionario: Funcionario, itens: list, motivo: str, deposito: Deposito, usuario_solicitante):
        """
        Cria solicitação de material e prepara movimentos de estoque

        Args:
            funcionario: Funcionário solicitante
            itens: Lista de dicts {'produto': produto_obj, 'quantidade': decimal}
            motivo: Motivo da solicitação
            deposito: Depósito de origem
            usuario_solicitante: Usuário que está fazendo a solicitação

        Returns:
            SolicitacaoMaterial: Objeto da solicitação criada
        """
        # 1. Criar a solicitação de material
        solicitacao = SolicitacaoMaterial.objects.create(
            funcionario=funcionario,
            tenant=funcionario.tenant,
            motivo=motivo,
            deposito_origem=deposito,
            solicitante_user=usuario_solicitante,
            status="pendente",
        )

        # 2. Criar os itens da solicitação
        for item_data in itens:
            produto = item_data["produto"]
            quantidade = item_data["quantidade"]

            # Verificar disponibilidade no estoque
            try:
                saldo = EstoqueSaldo.objects.get(produto=produto, deposito=deposito, tenant=funcionario.tenant)
                disponivel = saldo.disponivel()
            except EstoqueSaldo.DoesNotExist:
                disponivel = 0

            # Criar item da solicitação
            item_solicitacao = ItemSolicitacaoMaterial.objects.create(
                solicitacao=solicitacao,
                tenant=funcionario.tenant,
                produto=produto,
                quantidade_solicitada=quantidade,
                status="pendente",
                disponivel_estoque=disponivel,
            )

            # Se não aprovação automática está habilitada e há estoque, criar movimento
            if (
                solicitacao.aprovacao_automatica
                and disponivel >= quantidade
                and funcionario.perfil_estoque.pode_retirar_materiais
            ):
                EstoqueIntegrationService._criar_movimento_estoque(solicitacao, item_solicitacao, usuario_solicitante)

        return solicitacao

    @staticmethod
    @transaction.atomic
    def aprovar_solicitacao(solicitacao: SolicitacaoMaterial, aprovador_user, observacoes: str = ""):
        """
        Aprova solicitação e cria movimentos de estoque
        """
        if solicitacao.status != "pendente":
            raise ValueError("Solicitação não está pendente")

        # Atualizar status da solicitação
        solicitacao.status = "aprovada"
        solicitacao.aprovada_por_user = aprovador_user
        solicitacao.aprovada_em = timezone.now()
        solicitacao.observacoes_aprovacao = observacoes
        solicitacao.save()

        # Criar movimentos para cada item
        for item in solicitacao.itens.filter(status="pendente"):
            EstoqueIntegrationService._criar_movimento_estoque(solicitacao, item, aprovador_user)

    @staticmethod
    def _criar_movimento_estoque(solicitacao: SolicitacaoMaterial, item: ItemSolicitacaoMaterial, usuario_executante):
        """
        Cria movimento de estoque utilizando o sistema existente
        APROVEITAMENTO DA INFRAESTRUTURA EXISTENTE
        """
        # Verificar disponibilidade novamente
        try:
            saldo = EstoqueSaldo.objects.get(
                produto=item.produto, deposito=solicitacao.deposito_origem, tenant=solicitacao.tenant
            )
            if saldo.disponivel() < item.quantidade_solicitada:
                item.status = "indisponivel"
                item.save()
                return False
        except EstoqueSaldo.DoesNotExist:
            item.status = "indisponivel"
            item.save()
            return False

        # CRIAR MOVIMENTO NO SISTEMA EXISTENTE
        movimento = MovimentoEstoque.objects.create(
            produto=item.produto,
            tenant=solicitacao.tenant,
            deposito_origem=solicitacao.deposito_origem,
            tipo="SAIDA",
            quantidade=item.quantidade_solicitada,
            usuario_executante=usuario_executante,
            # INTEGRAÇÃO INTELIGENTE - USAR CAMPOS EXISTENTES
            solicitante_tipo="funcionario",
            solicitante_id=str(solicitacao.funcionario.id),
            solicitante_nome_cache=solicitacao.funcionario.nome_completo,
            ref_externa=f"SOL-{solicitacao.numero}",
            motivo=f"Retirada de material - {solicitacao.motivo}",
            metadata={
                "solicitacao_id": solicitacao.id,
                "item_solicitacao_id": item.id,
                "tipo_solicitante": "funcionario",
                "modulo_origem": "funcionarios",
            },
        )

        # Atualizar item
        item.status = "entregue"
        item.movimento_estoque = movimento  # Assumindo que existe FK
        item.entregue_em = timezone.now()
        item.save()

        # Criar registro de responsabilidade
        EstoqueIntegrationService._criar_responsabilidade_material(solicitacao, item, movimento)

        return True

    @staticmethod
    def _criar_responsabilidade_material(solicitacao, item, movimento):
        """
        Cria registro de responsabilidade do material pelo funcionário
        """
        ResponsabilidadeMaterial.objects.create(
            funcionario=solicitacao.funcionario,
            tenant=solicitacao.tenant,
            produto=item.produto,
            quantidade=item.quantidade_solicitada,
            movimento_origem=movimento,
            solicitacao_origem=solicitacao,
            status="ativo",
            data_retirada=timezone.now(),
            observacoes=f"Retirada via solicitação {solicitacao.numero}",
        )

    @staticmethod
    def get_historico_funcionario(funcionario: Funcionario, dias: int = 30):
        """
        Recupera histórico de movimentações do funcionário usando sistema existente
        """
        return (
            MovimentoEstoque.objects.filter(
                tenant=funcionario.tenant,
                solicitante_tipo="funcionario",
                solicitante_id=str(funcionario.id),
                criado_em__gte=timezone.now() - timezone.timedelta(days=dias),
            )
            .select_related("produto", "deposito_origem")
            .order_by("-criado_em")
        )

    @staticmethod
    def get_materiais_sob_responsabilidade(funcionario: Funcionario):
        """
        Lista materiais sob responsabilidade do funcionário
        """
        return (
            ResponsabilidadeMaterial.objects.filter(funcionario=funcionario, status="ativo")
            .select_related("produto")
            .order_by("-data_retirada")
        )

    @staticmethod
    @transaction.atomic
    def devolver_material(
        responsabilidade: ResponsabilidadeMaterial,
        quantidade_devolvida,
        usuario_executor,
        deposito_destino,
        motivo="Devolução",
    ):
        """
        Processa devolução de material criando movimento de entrada
        """
        if quantidade_devolvida > responsabilidade.quantidade:
            raise ValueError("Quantidade de devolução maior que a responsabilidade")

        # Criar movimento de entrada
        movimento_entrada = MovimentoEstoque.objects.create(
            produto=responsabilidade.produto,
            tenant=responsabilidade.tenant,
            deposito_destino=deposito_destino,
            tipo="ENTRADA",
            quantidade=quantidade_devolvida,
            usuario_executante=usuario_executor,
            solicitante_tipo="funcionario",
            solicitante_id=str(responsabilidade.funcionario.id),
            solicitante_nome_cache=responsabilidade.funcionario.nome_completo,
            ref_externa=f"DEV-{responsabilidade.id}",
            motivo=motivo,
            metadata={
                "responsabilidade_id": responsabilidade.id,
                "tipo_operacao": "devolucao",
                "movimento_origem_id": responsabilidade.movimento_origem.id,
                "modulo_origem": "funcionarios",
            },
        )

        # Atualizar responsabilidade
        responsabilidade.quantidade -= quantidade_devolvida
        if responsabilidade.quantidade == 0:
            responsabilidade.status = "devolvido"
            responsabilidade.data_devolucao = timezone.now()
        responsabilidade.save()

        return movimento_entrada


# Wrapper functions para facilitar o uso
def solicitar_material_funcionario(funcionario_id: int, itens: list, motivo: str, deposito_id: int, usuario):
    """Função helper para solicitação de material"""
    funcionario = Funcionario.objects.get(id=funcionario_id)
    deposito = Deposito.objects.get(id=deposito_id)
    return EstoqueIntegrationService.solicitar_material(funcionario, itens, motivo, deposito, usuario)


def aprovar_solicitacao_funcionario(solicitacao_id: int, aprovador, observacoes=""):
    """Função helper para aprovação"""
    solicitacao = SolicitacaoMaterial.objects.get(id=solicitacao_id)
    return EstoqueIntegrationService.aprovar_solicitacao(solicitacao, aprovador, observacoes)

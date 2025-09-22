"""
Sistema de Workflow para Aprovações de Operações de Estoque
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from estoque.models import Deposito, EstoqueSaldo, LogAuditoriaEstoque, MovimentoEstoque
from produtos.models import Produto

User = get_user_model()


class WorkflowAprovacao:
    """Sistema de workflow para aprovações de movimentos especiais"""

    OPERACOES_NECESSITAM_APROVACAO = ["DESCARTE", "PERDA", "VENCIMENTO", "DANIFICADO"]

    @classmethod
    def necessita_aprovacao(cls, tipo_movimento, valor_unitario=None, quantidade=None):
        """
        Verifica se movimento necessita aprovação
        """
        # Movimentos especiais sempre precisam de aprovação
        if tipo_movimento in cls.OPERACOES_NECESSITAM_APROVACAO:
            return True

        # Movimentos de alto valor (acima de R$ 1.000)
        if valor_unitario and quantidade:
            valor_total = valor_unitario * quantidade
            if valor_total > Decimal("1000.00"):
                return True

        return False

    @classmethod
    @transaction.atomic
    def criar_solicitacao_aprovacao(
        cls,
        produto_id,
        deposito_id,
        tipo,
        quantidade,
        valor_unitario,
        motivo,
        evidencias_ids=None,
        usuario_solicitante=None,
        tenant=None,
        observacoes=None,
    ):
        """
        Cria solicitação de aprovação para movimento
        """
        produto = Produto.objects.get(id=produto_id)
        deposito = Deposito.objects.get(id=deposito_id)

        # Verificar se realmente necessita aprovação
        if not cls.necessita_aprovacao(tipo, valor_unitario, quantidade):
            raise ValidationError("Este tipo de movimento não necessita aprovação")

        # Verificar saldo para movimentos de saída
        if tipo in cls.OPERACOES_NECESSITAM_APROVACAO:
            try:
                saldo = EstoqueSaldo.objects.get(produto=produto, deposito=deposito, tenant=tenant)
                if saldo.disponivel < quantidade:
                    raise ValidationError(f"Saldo insuficiente. Disponível: {saldo.disponivel}")
            except EstoqueSaldo.DoesNotExist:
                raise ValidationError("Produto não possui saldo neste depósito")

        # Criar movimento pendente de aprovação
        movimento = MovimentoEstoque.objects.create(
            produto=produto,
            deposito=deposito,
            tipo=tipo,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            motivo=motivo,
            observacoes=observacoes,
            usuario=usuario_solicitante,
            status_aprovacao="PENDENTE",
            tenant=tenant,
        )

        # Log de solicitação
        LogAuditoriaEstoque.objects.create(
            tipo="SOLICITACAO_APROVACAO",
            produto=produto,
            deposito=deposito,
            quantidade=quantidade,
            usuario=usuario_solicitante,
            motivo=f"Solicitação de aprovação para {tipo}: {motivo}",
            evidencias_ids=evidencias_ids or [],
            metadata={
                "movimento_id": movimento.id,
                "tipo_movimento": tipo,
                "valor_unitario": str(valor_unitario),
                "valor_total": str(valor_unitario * quantidade),
            },
            tenant=tenant,
        )

        return movimento

    @classmethod
    @transaction.atomic
    def aprovar_movimento(cls, movimento_id, usuario_aprovador, justificativa=None, evidencias_complementares=None):
        """
        Aprova movimento pendente
        """
        movimento = MovimentoEstoque.objects.select_for_update().get(id=movimento_id)

        if movimento.status_aprovacao != "PENDENTE":
            raise ValidationError("Movimento não está pendente de aprovação")

        # Verificar se aprovador tem permissão (poderia ser implementado)
        # if not cls._pode_aprovar(usuario_aprovador, movimento):
        #     raise ValidationError("Usuário sem permissão para aprovar")

        # Re-verificar saldo no momento da aprovação
        if movimento.tipo in cls.OPERACOES_NECESSITAM_APROVACAO:
            saldo = EstoqueSaldo.objects.select_for_update().get(
                produto=movimento.produto, deposito=movimento.deposito, tenant=movimento.tenant
            )

            if saldo.disponivel < movimento.quantidade:
                raise ValidationError(f"Saldo insuficiente no momento da aprovação. Disponível: {saldo.disponivel}")

        # Atualizar movimento
        movimento.status_aprovacao = "APROVADO"
        movimento.aprovado_em = timezone.now()
        movimento.aprovado_por = usuario_aprovador
        movimento.justificativa_aprovacao = justificativa

        # Processar movimento (atualizar saldos)
        if movimento.tipo in cls.OPERACOES_NECESSITAM_APROVACAO:
            # Movimento de saída
            saldo.fisico -= movimento.quantidade
            saldo.save()

            # Calcular valor médio se necessário
            if saldo.fisico > 0 and movimento.valor_unitario > 0:
                # Recalcular valor médio ponderado
                valor_total_restante = (saldo.fisico * saldo.valor_medio_unitario) - (
                    movimento.quantidade * movimento.valor_unitario
                )
                if valor_total_restante > 0:
                    saldo.valor_medio_unitario = valor_total_restante / saldo.fisico
                saldo.save()

        movimento.save()

        # Log de aprovação
        LogAuditoriaEstoque.objects.create(
            tipo="MOVIMENTO_APROVADO",
            produto=movimento.produto,
            deposito=movimento.deposito,
            quantidade=movimento.quantidade,
            usuario=usuario_aprovador,
            motivo=f"Aprovação de {movimento.tipo}: {justificativa or 'Sem justificativa'}",
            evidencias_ids=evidencias_complementares or [],
            metadata={
                "movimento_id": movimento.id,
                "aprovado_por_id": usuario_aprovador.id,
                "aprovado_por_nome": usuario_aprovador.get_full_name(),
                "tipo_movimento": movimento.tipo,
                "motivo_original": movimento.motivo,
            },
            tenant=movimento.tenant,
        )

        return movimento

    @classmethod
    @transaction.atomic
    def rejeitar_movimento(cls, movimento_id, usuario_rejeitador, motivo_rejeicao, evidencias_rejeicao=None):
        """
        Rejeita movimento pendente
        """
        movimento = MovimentoEstoque.objects.select_for_update().get(id=movimento_id)

        if movimento.status_aprovacao != "PENDENTE":
            raise ValidationError("Movimento não está pendente de aprovação")

        # Atualizar movimento
        movimento.status_aprovacao = "REJEITADO"
        movimento.rejeitado_em = timezone.now()
        movimento.rejeitado_por = usuario_rejeitador
        movimento.motivo_rejeicao = motivo_rejeicao
        movimento.save()

        # Log de rejeição
        LogAuditoriaEstoque.objects.create(
            tipo="MOVIMENTO_REJEITADO",
            produto=movimento.produto,
            deposito=movimento.deposito,
            quantidade=movimento.quantidade,
            usuario=usuario_rejeitador,
            motivo=f"Rejeição de {movimento.tipo}: {motivo_rejeicao}",
            evidencias_ids=evidencias_rejeicao or [],
            metadata={
                "movimento_id": movimento.id,
                "rejeitado_por_id": usuario_rejeitador.id,
                "rejeitado_por_nome": usuario_rejeitador.get_full_name(),
                "tipo_movimento": movimento.tipo,
                "motivo_original": movimento.motivo,
                "motivo_rejeicao": motivo_rejeicao,
            },
            tenant=movimento.tenant,
        )

        return movimento

    @classmethod
    def listar_pendentes_aprovacao(cls, usuario=None, tenant=None):
        """
        Lista movimentos pendentes de aprovação
        """
        queryset = (
            MovimentoEstoque.objects.filter(status_aprovacao="PENDENTE")
            .select_related("produto", "deposito", "usuario")
            .order_by("criado_em")
        )

        if tenant:
            queryset = queryset.filter(tenant=tenant)

        return queryset

    @classmethod
    def estatisticas_aprovacao(cls, tenant=None, dias=30):
        """
        Estatísticas de aprovações
        """
        from datetime import timedelta

        from django.db.models import Count, Q, Sum

        data_limite = timezone.now() - timedelta(days=dias)

        queryset = MovimentoEstoque.objects.filter(criado_em__gte=data_limite)

        if tenant:
            queryset = queryset.filter(tenant=tenant)

        stats = queryset.aggregate(
            total_solicitacoes=Count("id", filter=Q(status_aprovacao__isnull=False)),
            pendentes=Count("id", filter=Q(status_aprovacao="PENDENTE")),
            aprovadas=Count("id", filter=Q(status_aprovacao="APROVADO")),
            rejeitadas=Count("id", filter=Q(status_aprovacao="REJEITADO")),
            valor_aprovado=Sum("valor_unitario", filter=Q(status_aprovacao="APROVADO")),
            valor_rejeitado=Sum("valor_unitario", filter=Q(status_aprovacao="REJEITADO")),
        )

        # Calcular tempo médio de aprovação
        movimentos_aprovados = queryset.filter(status_aprovacao="APROVADO", aprovado_em__isnull=False)

        tempos_aprovacao = []
        for mov in movimentos_aprovados:
            if mov.aprovado_em and mov.criado_em:
                tempo = (mov.aprovado_em - mov.criado_em).total_seconds() / 3600  # horas
                tempos_aprovacao.append(tempo)

        if tempos_aprovacao:
            stats["tempo_medio_aprovacao_horas"] = sum(tempos_aprovacao) / len(tempos_aprovacao)
        else:
            stats["tempo_medio_aprovacao_horas"] = 0

        return stats

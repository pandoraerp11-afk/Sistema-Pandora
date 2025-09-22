# prontuarios/services.py
from django.db import transaction

from agendamentos.models import Agendamento

from .models import Atendimento


class AtendimentoAgendamentoService:
    """
    Service para sincronizar estados entre Agendamento e Atendimento
    """

    @staticmethod
    @transaction.atomic
    def iniciar_atendimento(agendamento_id):
        """
        Marca agendamento como EM_ANDAMENTO e cria/atualiza atendimento
        """
        try:
            agendamento = Agendamento.objects.select_for_update().get(id=agendamento_id)

            if agendamento.status != "CONFIRMADO":
                raise ValueError(f"Agendamento deve estar CONFIRMADO. Status atual: {agendamento.status}")

            # Atualizar agendamento
            agendamento.status = "EM_ANDAMENTO"
            agendamento.save()

            # Criar ou atualizar atendimento
            atendimento, created = Atendimento.objects.get_or_create(
                agendamento=agendamento,
                defaults={
                    "tenant": agendamento.tenant,
                    "cliente": agendamento.cliente,
                    # migração: usar servico unificado em vez de procedimento
                    "servico": getattr(agendamento, "servico", None),
                    "profissional": agendamento.profissional,
                    "data_atendimento": agendamento.data_inicio,
                    "numero_sessao": 1,
                    "status": "EM_ANDAMENTO",
                    "origem_agendamento": agendamento.origem,
                    "valor_cobrado": (getattr(getattr(agendamento, "servico", None), "valor_base", None) or 0),
                    "forma_pagamento": "A_DEFINIR",
                },
            )

            if not created:
                atendimento.status = "EM_ANDAMENTO"
                atendimento.save()

            return atendimento, created

        except Agendamento.DoesNotExist:
            raise ValueError(f"Agendamento {agendamento_id} não encontrado")

    @staticmethod
    @transaction.atomic
    def concluir_atendimento(atendimento_id, dados_conclusao=None):
        """
        Marca atendimento como CONCLUÍDO e sincroniza agendamento
        """
        try:
            atendimento = Atendimento.objects.select_for_update().get(id=atendimento_id)

            if atendimento.status not in ["EM_ANDAMENTO", "AGENDADO"]:
                raise ValueError(f"Atendimento deve estar EM_ANDAMENTO ou AGENDADO. Status: {atendimento.status}")

            # Atualizar dados do atendimento
            atendimento.status = "CONCLUIDO"

            if dados_conclusao:
                for campo, valor in dados_conclusao.items():
                    if hasattr(atendimento, campo):
                        setattr(atendimento, campo, valor)

            atendimento.save()

            # Sincronizar agendamento
            if atendimento.agendamento:
                atendimento.agendamento.status = "CONCLUIDO"
                atendimento.agendamento.save()

            return atendimento

        except Atendimento.DoesNotExist:
            raise ValueError(f"Atendimento {atendimento_id} não encontrado")

    @staticmethod
    @transaction.atomic
    def cancelar_agendamento_com_atendimento(agendamento_id, motivo=None):
        """
        Cancela agendamento e atendimento vinculado (se existir)
        """
        try:
            agendamento = Agendamento.objects.select_for_update().get(id=agendamento_id)

            # Cancelar agendamento
            agendamento.status = "CANCELADO"
            agendamento.save()

            # Cancelar atendimento vinculado (se existir)
            atendimentos = agendamento.atendimentos_clinicos.all()
            for atendimento in atendimentos:
                if atendimento.status not in ["CONCLUIDO", "CANCELADO"]:
                    atendimento.status = "CANCELADO"
                    if motivo:
                        atendimento.observacoes_pos_procedimento = f"Cancelado: {motivo}"
                    atendimento.save()

            # Liberar slot se vinculado
            if agendamento.slot:
                agendamento.slot.capacidade_utilizada = max(0, agendamento.slot.capacidade_utilizada - 1)
                agendamento.slot.save()

            return agendamento, list(atendimentos)

        except Agendamento.DoesNotExist:
            raise ValueError(f"Agendamento {agendamento_id} não encontrado")

    @staticmethod
    def obter_status_integrado(agendamento_id):
        """
        Retorna status consolidado do agendamento e atendimento
        """
        try:
            agendamento = Agendamento.objects.get(id=agendamento_id)
            atendimentos = list(agendamento.atendimentos_clinicos.all())

            return {
                "agendamento": {
                    "id": agendamento.id,
                    "status": agendamento.status,
                    "data_inicio": agendamento.data_inicio,
                    "data_fim": agendamento.data_fim,
                },
                "atendimentos": [
                    {
                        "id": at.id,
                        "status": at.status,
                        "data_atendimento": at.data_atendimento,
                        "valor_cobrado": at.valor_cobrado,
                        "satisfacao_cliente": at.satisfacao_cliente,
                    }
                    for at in atendimentos
                ],
                "pode_iniciar": agendamento.status == "CONFIRMADO",
                "pode_cancelar": agendamento.status in ["CONFIRMADO", "PENDENTE"],
                "esta_em_andamento": agendamento.status == "EM_ANDAMENTO",
                "foi_concluido": agendamento.status == "CONCLUIDO",
            }

        except Agendamento.DoesNotExist:
            return None

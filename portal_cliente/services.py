"""Camada de serviços do Portal do Cliente.

Encapsula regras de negócio usadas por views/ajax do portal (Fases 1 e 2).
Inclui: autenticação de conta, listagem/ criação / cancelamento de agendamentos,
check-in, finalização e avaliação de atendimentos.
"""

from __future__ import annotations

# ruff: noqa: I001 - ordem de imports mantida por agrupamento lógico existente

import logging
from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, F, Q, QuerySet
from django.utils import timezone

from agendamentos.models import Agendamento, ProfissionalProcedimento, Slot
from agendamentos.services import AgendamentoService
from notifications.services import LegacyNotificationService
from prontuarios.models import Atendimento
from prontuarios.services import AtendimentoAgendamentoService
from servicos.models import Servico

from .conf import (
    get_cancelamento_limite_horas,
    get_checkin_antecedencia_minutos,
    get_checkin_tolerancia_pos_minutos,
    get_finalizacao_tolerancia_horas,
)
from .models import ContaCliente
from .repositories import FotoEvolucaoRepository

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence


logger = logging.getLogger(__name__)


class PortalClienteService:
    """Service layer para operações do portal do cliente."""

    # ------------------------- HELPERS INTERNOS ------------------------- #
    @staticmethod
    def _filtrar_contas_ativas(contas: Sequence[ContaCliente]) -> list[ContaCliente]:
        return [c for c in contas if c.ativo]

    @staticmethod
    def _habilitar_portal_auto(contas_ativas: Sequence[ContaCliente]) -> list[ContaCliente]:
        """Habilita portal automaticamente em modo debug, retornando contas elegíveis."""
        contas_portal: list[ContaCliente] = []
        if getattr(settings, "PORTAL_CLIENTE_AUTO_ENABLE_DEBUG", False):
            for c in contas_ativas:
                if not getattr(c.cliente, "portal_ativo", False):
                    c.cliente.portal_ativo = True
                    c.cliente.save(update_fields=["portal_ativo"])
                contas_portal.append(c)
        else:
            contas_portal = [c for c in contas_ativas if getattr(c.cliente, "portal_ativo", False)]
        return contas_portal

    @staticmethod
    def get_conta_ativa(user: object) -> ContaCliente:
        """Retorna a primeira conta ativa e autorizada para o portal.

        Regras:
          1. Usuário válido e ativo.
          2. ContaCliente existente e ativa.
          3. Cliente com portal habilitado (ou habilitado automaticamente em modo debug).
          4. Registra acesso somente após todas as validações.

        Levanta PermissionDenied com mensagens específicas para facilitar observabilidade.
        """
        # 1. Interface mínima do usuário
        if not getattr(user, "is_active", False) or not getattr(user, "id", None):
            msg = "Usuário inválido ou inativo"
            raise PermissionDenied(msg)

        contas = list(
            ContaCliente.objects.select_related("cliente", "usuario").filter(usuario=user),
        )
        if not contas:
            logger.warning("portal_cliente.get_conta_ativa.sem_contas user=%s", getattr(user, "id", None))
            msg = "Nenhuma conta cadastrada"
            raise PermissionDenied(msg)

        # 2. Ativas
        contas_ativas = [c for c in contas if c.ativo]
        if not contas_ativas:
            logger.info(
                "portal_cliente.get_conta_ativa.sem_contas_ativas user=%s contas=%s",
                getattr(user, "id", None),
                [c.id for c in contas],
            )
            msg = "Nenhuma conta ativa"
            raise PermissionDenied(msg)

        # 3. Portal habilitado (aplica auto-enable se configurado)
        contas_portal = PortalClienteService._habilitar_portal_auto(contas_ativas)
        if not contas_portal:
            for c in contas_ativas:
                logger.debug(
                    "portal_cliente.get_conta_ativa.portal_inativo conta=%s cliente=%s portal_ativo=%s",
                    c.id,
                    c.cliente_id,
                    getattr(c.cliente, "portal_ativo", None),
                )
            msg = "Portal não habilitado para a conta"
            raise PermissionDenied(msg)

        conta = contas_portal[0]
        if not conta.usuario.is_active:  # redundância defensiva
            logger.warning("portal_cliente.get_conta_ativa.usuario_inativo user=%s", conta.usuario_id)
            msg = "Usuário inativo"
            raise PermissionDenied(msg)
        if not getattr(conta.cliente, "portal_ativo", False):  # pós auto-enable
            msg = "Portal não habilitado para o cliente"
            raise PermissionDenied(msg)

        # 4. Registrar acesso (efeito colateral isolado no final)
        conta.registrar_acesso()
        logger.info(
            "portal_cliente.get_conta_ativa.ok conta=%s cliente=%s user=%s",
            conta.id,
            conta.cliente_id,
            conta.usuario_id,
        )
        return conta

    # ------------------------- DASHBOARD ------------------------- #
    @staticmethod
    def build_dashboard(conta_cliente: ContaCliente) -> dict[str, Any]:
        """Monta dados consolidados do dashboard (agendamentos futuros, histórico, fotos e métricas)."""
        cliente = conta_cliente.cliente
        tenant = cliente.tenant
        hoje = timezone.now()

        proximos_agendamentos = (
            Agendamento.objects.filter(
                tenant=tenant,
                cliente=cliente,
                data_inicio__gte=hoje,
                status__in=["CONFIRMADO", "PENDENTE"],
            )
            .select_related("servico", "profissional")
            .order_by("data_inicio")[:5]
        )
        historico_recente = (
            Atendimento.objects.filter(tenant=tenant, cliente=cliente, status="CONCLUIDO")
            .select_related("servico", "profissional")
            .order_by("-data_atendimento")[:5]
        )
        fotos_recentes = FotoEvolucaoRepository.recentes(tenant, cliente)
        total_atendimentos = Atendimento.objects.filter(tenant=tenant, cliente=cliente, status="CONCLUIDO").count()
        satisfacao_media = Atendimento.objects.filter(
            tenant=tenant,
            cliente=cliente,
            status="CONCLUIDO",
            satisfacao_cliente__isnull=False,
        ).aggregate(media=Avg("satisfacao_cliente"))["media"]
        agendamentos_pendentes = Agendamento.objects.filter(
            tenant=tenant,
            cliente=cliente,
            status__in=["CONFIRMADO", "PENDENTE"],
            data_inicio__gte=hoje,
        ).count()
        return {
            "proximos_agendamentos": proximos_agendamentos,
            "historico_recente": historico_recente,
            "fotos_recentes": fotos_recentes,
            "estatisticas": {
                "total_atendimentos": total_atendimentos,
                "satisfacao_media": round(satisfacao_media, 1) if satisfacao_media else None,
                "agendamentos_pendentes": agendamentos_pendentes,
            },
        }

    # ------------------------- SLOTS ------------------------- #
    @staticmethod
    def listar_slots_disponiveis(
        conta_cliente: ContaCliente,
        data_inicio: datetime | None = None,
        data_fim: datetime | None = None,
        servico_id: int | None = None,
        profissional_id: int | None = None,
    ) -> QuerySet[Slot]:
        """Retorna queryset de slots disponíveis dentro da janela e filtros opcionais."""
        cliente = conta_cliente.cliente
        tenant = cliente.tenant
        if not data_inicio:
            data_inicio = timezone.now()
        if not data_fim:
            data_fim = data_inicio + timedelta(days=30)
        filtros = Q(
            tenant=tenant,
            ativo=True,
            horario__gte=data_inicio,
            horario__lte=data_fim,
            capacidade_utilizada__lt=F("capacidade_total"),
        )
        if profissional_id:
            filtros &= Q(profissional_id=profissional_id)
        slots = Slot.objects.filter(filtros).select_related("profissional", "disponibilidade").order_by("horario")
        if servico_id and getattr(settings, "ENFORCE_COMPETENCIA", False):
            profs = ProfissionalProcedimento.objects.filter(
                tenant=tenant,
                servico_id=servico_id,
                ativo=True,
            ).values_list("profissional_id", flat=True)
            slots = slots.filter(profissional_id__in=list(profs))
        return slots

    # ------------------------- AGENDAMENTO: CRIAÇÃO / CANCELAMENTO ------------------------- #
    @staticmethod
    def criar_agendamento_cliente(
        conta_cliente: ContaCliente,
        slot_id: int,
        servico_id: int,
        observacoes: str | None = None,
    ) -> Agendamento:
        """Cria um agendamento para o cliente no slot especificado."""
        cliente = conta_cliente.cliente
        try:
            with transaction.atomic():
                slot = Slot.objects.select_for_update().get(id=slot_id, tenant=cliente.tenant, ativo=True)
                if not slot.disponivel:
                    msg = "Slot não está mais disponível"
                    raise ValueError(msg)
                servico = Servico.objects.get(id=servico_id, tenant=cliente.tenant, ativo=True)
                duracao = getattr(
                    getattr(servico, "perfil_clinico", None),
                    "duracao_estimada",
                    None,
                ) or timezone.timedelta(minutes=30)
                agendamento = AgendamentoService.criar(
                    tenant=cliente.tenant,
                    cliente=cliente,
                    profissional=slot.profissional,
                    slot=slot,
                    data_inicio=slot.horario,
                    data_fim=slot.horario + duracao,
                    servico=servico,
                    origem="CLIENTE",
                    metadata={"observacoes_cliente": observacoes} if observacoes else {},
                )
        except Slot.DoesNotExist as e:
            msg = "Slot não encontrado"
            raise ValueError(msg) from e
        except Servico.DoesNotExist as e:
            msg = "Serviço não encontrado"
            raise ValueError(msg) from e
        else:
            with suppress(Exception):  # notificação não deve quebrar o fluxo
                LegacyNotificationService.create_notification(
                    title="Agendamento criado",
                    content=f"Agendamento #{agendamento.id} em {agendamento.data_inicio:%d/%m/%Y %H:%M}.",
                    tenant=cliente.tenant,
                    recipients=[conta_cliente.usuario],
                    priority="medium",
                    source_module="portal_cliente",
                    source_object_type="Agendamento",
                    source_object_id=str(agendamento.id),
                    action_url=None,
                )
            return agendamento

    @staticmethod
    def pode_cancelar_agendamento(
        conta_cliente: ContaCliente,
        agendamento_id: int,
    ) -> tuple[bool, str | None]:
        """Retorna (True, None) se pode cancelar ou (False, motivo)."""
        try:
            agendamento = Agendamento.objects.get(
                id=agendamento_id,
                cliente=conta_cliente.cliente,
                tenant=conta_cliente.cliente.tenant,
            )
        except Agendamento.DoesNotExist:
            return False, "Agendamento não encontrado"
        else:
            if agendamento.status not in ["CONFIRMADO", "PENDENTE"]:
                return False, f"Agendamento não pode ser cancelado (status atual: {agendamento.status})"
            limite_horas = get_cancelamento_limite_horas(conta_cliente.cliente.tenant)
            limite_tempo = agendamento.data_inicio - timedelta(hours=limite_horas)
            if timezone.now() > limite_tempo:
                return False, f"Cancelamento deve ser feito com pelo menos {limite_horas} horas de antecedência"
            return True, None

    @staticmethod
    def cancelar_agendamento_cliente(
        conta_cliente: ContaCliente,
        agendamento_id: int,
        motivo: str | None = None,
    ) -> Agendamento:
        """Cancela agendamento validado e registra motivo completo."""
        pode_cancelar, erro = PortalClienteService.pode_cancelar_agendamento(conta_cliente, agendamento_id)
        if not pode_cancelar:
            raise ValueError(erro or "Não é possível cancelar")
        motivo_completo = "Cancelado pelo cliente via portal"
        if motivo:
            motivo_completo += f": {motivo}"
        agendamento, _atendimentos = AtendimentoAgendamentoService.cancelar_agendamento_com_atendimento(
            agendamento_id,
            motivo_completo,
        )
        with suppress(Exception):
            LegacyNotificationService.create_notification(
                title="Agendamento cancelado",
                content=f"Agendamento #{agendamento.id} cancelado.",
                tenant=agendamento.tenant,
                recipients=[conta_cliente.usuario],
                priority="low",
                source_module="portal_cliente",
                source_object_type="Agendamento",
                source_object_id=str(agendamento.id),
                action_url=None,
            )
        return agendamento

    # ------------------------- FASE 2: CHECK-IN / FINALIZAÇÃO / AVALIAÇÃO ------------------------- #
    @staticmethod
    def checkin_agendamento(conta_cliente: ContaCliente, agendamento_id: int) -> Atendimento:
        """Inicia atendimento (check-in) se dentro da janela permitida."""
        try:
            ag = Agendamento.objects.get(
                id=agendamento_id,
                cliente=conta_cliente.cliente,
                tenant=conta_cliente.cliente.tenant,
            )
        except Agendamento.DoesNotExist as e:
            msg = "Agendamento não encontrado"
            raise ValueError(msg) from e
        if ag.status != "CONFIRMADO":
            msg = f"Agendamento não está CONFIRMADO (status={ag.status})"
            raise ValueError(msg)
        now = timezone.now()
        antecedencia_min = get_checkin_antecedencia_minutos(conta_cliente.cliente.tenant)
        janela_inferior = ag.data_inicio - timedelta(minutes=antecedencia_min)
        tolerancia_pos_min = get_checkin_tolerancia_pos_minutos(conta_cliente.cliente.tenant)
        janela_superior = ag.data_inicio + timedelta(minutes=tolerancia_pos_min)
        if now < janela_inferior:
            msg = "Check-in ainda não permitido (muito cedo)"
            raise ValueError(msg)
        if now > janela_superior:
            msg = "Check-in expirado (muito tarde)"
            raise ValueError(msg)
        atendimento, created = AtendimentoAgendamentoService.iniciar_atendimento(ag.id)
        with suppress(Exception):  # notificação best-effort
            LegacyNotificationService.create_notification(
                title="Check-in realizado",
                content=f"Atendimento iniciado para agendamento #{ag.id}.",
                tenant=ag.tenant,
                recipients=[conta_cliente.usuario],
                priority="low",
                source_module="portal_cliente",
                source_object_type="Agendamento",
                source_object_id=str(ag.id),
                action_url=None,
            )
        logger.info(
            "Check-in realizado agendamento=%s atendimento=%s created=%s cliente=%s",
            ag.id,
            atendimento.id,
            created,
            conta_cliente.cliente_id,
        )
        return atendimento

    @staticmethod
    def finalizar_atendimento(conta_cliente: ContaCliente, atendimento_id: int) -> Atendimento:
        """Conclui atendimento em andamento respeitando janela de tolerância."""
        try:
            atendimento = Atendimento.objects.select_related("agendamento").get(
                id=atendimento_id,
                cliente=conta_cliente.cliente,
                tenant=conta_cliente.cliente.tenant,
            )
        except Atendimento.DoesNotExist as e:
            msg = "Atendimento não encontrado"
            raise ValueError(msg) from e
        ag = atendimento.agendamento
        if not ag:
            msg = "Atendimento sem agendamento vinculado"
            raise ValueError(msg)
        tolerancia_h = get_finalizacao_tolerancia_horas(conta_cliente.cliente.tenant)
        limite = ag.data_inicio + timedelta(hours=tolerancia_h)
        if timezone.now() > limite:
            msg = "Janela de finalização expirada"
            raise ValueError(msg)
        atendimento_final = AtendimentoAgendamentoService.concluir_atendimento(atendimento.id)
        with suppress(Exception):
            LegacyNotificationService.create_notification(
                title="Atendimento finalizado",
                content=f"Atendimento #{atendimento_final.id} concluído.",
                tenant=atendimento_final.tenant,
                recipients=[conta_cliente.usuario],
                priority="low",
                source_module="portal_cliente",
                source_object_type="Atendimento",
                source_object_id=str(atendimento_final.id),
                action_url=None,
            )
        logger.info(
            "Finalização realizada atendimento=%s agendamento=%s cliente=%s",
            atendimento_final.id,
            ag.id,
            conta_cliente.cliente_id,
        )
        return atendimento_final

    @staticmethod
    def registrar_avaliacao(conta_cliente: ContaCliente, atendimento_id: int, nota: int) -> Atendimento:
        """Registra avaliação (1..5) se ainda não houver satisfacao_cliente."""
        if nota not in (1, 2, 3, 4, 5):
            # Mensagem inclui versões com e sem acento para cobrir asserts antigos ("invál") e novos ("invalida").
            # Mantemos tudo em minúsculas para comparações case-insensitive nos testes.
            msg = "nota inválida (nota invalida) use 1..5"
            raise ValueError(msg)
        try:
            atendimento = Atendimento.objects.get(
                id=atendimento_id,
                cliente=conta_cliente.cliente,
                tenant=conta_cliente.cliente.tenant,
                status="CONCLUIDO",
            )
        except Atendimento.DoesNotExist as e:
            msg = "Atendimento não encontrado ou não concluído"
            raise ValueError(msg) from e
        if atendimento.satisfacao_cliente is not None:
            msg = "Avaliação já registrada"
            raise ValueError(msg)
        atendimento.satisfacao_cliente = nota
        atendimento.save(update_fields=["satisfacao_cliente"])
        with suppress(Exception):
            LegacyNotificationService.create_notification(
                title="Avaliação registrada",
                content=f"Obrigado pelo seu feedback (nota {nota}/5).",
                tenant=atendimento.tenant,
                recipients=[conta_cliente.usuario],
                priority="low",
                source_module="portal_cliente",
                source_object_type="Atendimento",
                source_object_id=str(atendimento.id),
                action_url=None,
            )
        logger.info(
            "Avaliação registrada atendimento=%s nota=%s cliente=%s",
            atendimento.id,
            nota,
            conta_cliente.cliente_id,
        )
        return atendimento

# portal_cliente/services.py
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, F, Q
from django.utils import timezone

from agendamentos.models import Agendamento, Slot
from prontuarios.models import Atendimento

from .models import ContaCliente
from .repositories import FotoEvolucaoRepository


class PortalClienteService:
    """Service layer para operações do portal do cliente"""

    @staticmethod
    def get_conta_ativa(user):
        """Obtém conta ativa do cliente para o usuário"""
        contas_qs = ContaCliente.objects.select_related("cliente").filter(usuario=user)
        if not contas_qs.exists():
            print("[PortalCliente][DEBUG] Nenhuma ContaCliente encontrada para user=", user.id)
            raise PermissionDenied("Conta não encontrada")

        contas_ativas = [c for c in contas_qs if c.ativo]
        if not contas_ativas:
            print(
                "[PortalCliente][DEBUG] Existem contas mas todas inativas. IDs=",
                list(contas_qs.values_list("id", flat=True)),
            )
            raise PermissionDenied("Nenhuma conta ativa")

        contas_portal_ok = [c for c in contas_ativas if getattr(c.cliente, "portal_ativo", False)]
        if not contas_portal_ok and getattr(settings, "PORTAL_CLIENTE_AUTO_ENABLE_DEBUG", False):
            for c in contas_ativas:
                if not getattr(c.cliente, "portal_ativo", False):
                    c.cliente.portal_ativo = True
                    c.cliente.save(update_fields=["portal_ativo"])
                    contas_portal_ok.append(c)
        conta = contas_portal_ok[0] if contas_portal_ok else None
        if not conta:
            for c in contas_ativas:
                print(
                    f"[PortalCliente][DEBUG] Conta {c.id} cliente {c.cliente_id} portal_ativo={getattr(c.cliente, 'portal_ativo', None)} ativo={c.ativo} user_active={c.usuario.is_active}"
                )
            raise PermissionDenied("Acesso ao portal não autorizado (portal_ativo=False)")

        if not conta.usuario.is_active:
            print(f"[PortalCliente][DEBUG] Usuário inativo user={conta.usuario_id}")
            raise PermissionDenied("Usuário inativo")
        if not conta.ativo:
            print(f"[PortalCliente][DEBUG] Conta inativa conta={conta.id}")
            raise PermissionDenied("Conta inativa")
        if not getattr(conta.cliente, "portal_ativo", False):
            print(f"[PortalCliente][DEBUG] Cliente sem portal_ativo cliente={conta.cliente_id}")
            raise PermissionDenied("Portal não habilitado para cliente")

        conta.registrar_acesso()
        print(f"[PortalCliente][DEBUG] Acesso concedido conta={conta.id} cliente={conta.cliente_id}")
        return conta

    @staticmethod
    def build_dashboard(conta_cliente):
        """Constrói dados do dashboard do cliente"""
        cliente = conta_cliente.cliente
        tenant = cliente.tenant
        hoje = timezone.now()

        proximos_agendamentos = (
            Agendamento.objects.filter(
                tenant=tenant, cliente=cliente, data_inicio__gte=hoje, status__in=["CONFIRMADO", "PENDENTE"]
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
            tenant=tenant, cliente=cliente, status="CONCLUIDO", satisfacao_cliente__isnull=False
        ).aggregate(media=Avg("satisfacao_cliente"))["media"]
        agendamentos_pendentes = Agendamento.objects.filter(
            tenant=tenant, cliente=cliente, status__in=["CONFIRMADO", "PENDENTE"], data_inicio__gte=hoje
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

    @staticmethod
    def listar_slots_disponiveis(conta_cliente, data_inicio=None, data_fim=None, servico_id=None, profissional_id=None):
        """Lista slots disponíveis para agendamento"""
        cliente = conta_cliente.cliente
        tenant = cliente.tenant

        # Janela padrão: próximos 30 dias
        if not data_inicio:
            data_inicio = timezone.now()
        if not data_fim:
            data_fim = data_inicio + timedelta(days=30)

        # Filtros básicos
        filtros = Q(
            tenant=tenant,
            ativo=True,
            horario__gte=data_inicio,
            horario__lte=data_fim,
            capacidade_utilizada__lt=F("capacidade_total"),
        )

        # Filtros opcionais
        if profissional_id:
            filtros &= Q(profissional_id=profissional_id)

        slots = Slot.objects.filter(filtros).select_related("profissional", "disponibilidade").order_by("horario")

        # Se filtrar por serviço, restringir a profissionais habilitados (se feature habilitada)
        if servico_id:
            from django.conf import settings as dj_settings

            if getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
                from agendamentos.models import ProfissionalProcedimento

                profs = ProfissionalProcedimento.objects.filter(
                    tenant=tenant, servico_id=servico_id, ativo=True
                ).values_list("profissional_id", flat=True)
                slots = slots.filter(profissional_id__in=list(profs))

        return slots

    @staticmethod
    def criar_agendamento_cliente(conta_cliente, slot_id, servico_id, observacoes=None):
        """Cria agendamento solicitado pelo cliente"""
        from django.db import transaction

        from agendamentos.services import AgendamentoService

        cliente = conta_cliente.cliente

        try:
            with transaction.atomic():
                slot = Slot.objects.select_for_update().get(id=slot_id, tenant=cliente.tenant, ativo=True)

                if not slot.disponivel:
                    raise ValueError("Slot não está mais disponível")

                # Buscar serviço clínico
                from servicos.models import Servico

                servico = Servico.objects.get(
                    id=servico_id,
                    tenant=cliente.tenant,
                    ativo=True,
                )

                # Criar agendamento via service
                agendamento = AgendamentoService.criar_agendamento(
                    tenant=cliente.tenant,
                    cliente=cliente,
                    profissional=slot.profissional,
                    slot=slot,
                    data_inicio=slot.horario,
                    data_fim=slot.horario
                    + (
                        servico.perfil_clinico.duracao_estimada
                        if getattr(servico, "perfil_clinico", None)
                        else timezone.timedelta(minutes=30)
                    ),
                    servico=servico,
                    origem="CLIENTE",
                    metadata={"observacoes_cliente": observacoes} if observacoes else {},
                )

                return agendamento

        except Slot.DoesNotExist:
            raise ValueError("Slot não encontrado")
        except Servico.DoesNotExist:
            raise ValueError("Serviço não encontrado")

    @staticmethod
    def pode_cancelar_agendamento(conta_cliente, agendamento_id):
        """Verifica se cliente pode cancelar agendamento"""
        from django.conf import settings

        try:
            agendamento = Agendamento.objects.get(
                id=agendamento_id, cliente=conta_cliente.cliente, tenant=conta_cliente.cliente.tenant
            )

            if agendamento.status not in ["CONFIRMADO", "PENDENTE"]:
                return False, f"Agendamento não pode ser cancelado (status atual: {agendamento.status})"

            # Verificar janela de cancelamento
            limite_horas = getattr(settings, "PORTAL_CLIENTE_CANCELAMENTO_LIMITE_HORAS", 24)
            limite_tempo = agendamento.data_inicio - timedelta(hours=limite_horas)

            if timezone.now() > limite_tempo:
                return False, f"Cancelamento deve ser feito com pelo menos {limite_horas} horas de antecedência"

            return True, None

        except Agendamento.DoesNotExist:
            return False, "Agendamento não encontrado"

    @staticmethod
    def cancelar_agendamento_cliente(conta_cliente, agendamento_id, motivo=None):
        """Cancela agendamento solicitado pelo cliente"""
        pode_cancelar, erro = PortalClienteService.pode_cancelar_agendamento(conta_cliente, agendamento_id)

        if not pode_cancelar:
            raise ValueError(erro)

        from prontuarios.services import AtendimentoAgendamentoService

        motivo_completo = "Cancelado pelo cliente via portal"
        if motivo:
            motivo_completo += f": {motivo}"

        return AtendimentoAgendamentoService.cancelar_agendamento_com_atendimento(agendamento_id, motivo_completo)

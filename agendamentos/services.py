"""Serviços de agenda (slots, agendamentos e fachada de orquestração).

Camada de serviços sem regras de negócio novas: contém operações atômicas de
reserva/geração de slots e criação/alteração de agendamentos, mais uma fachada
para instrumentação e compatibilidade. Este módulo também expõe métricas
opcionais via Prometheus, caindo em NoOp quando a lib não está disponível.
"""

from __future__ import annotations

import contextlib
import time
from datetime import datetime, timedelta
from time import monotonic
from typing import Any, Protocol

from django.conf import settings
from django.conf import settings as dj_settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from agendamentos.models import Agendamento, AuditoriaAgendamento, Disponibilidade, Slot, WaitlistEntry
from agendamentos.utils import notificar_profissional_e_clientes

_METRICS_ENABLED = False


class CounterLike(Protocol):
    """Interface mínima de um Counter de métricas."""

    def inc(self, amount: float = 1, exemplar: dict[str, str] | None = None) -> None:  # noqa: D102
        ...


class HistogramLike(Protocol):
    """Interface mínima de um Histograma de métricas."""

    def observe(self, amount: float, exemplar: dict[str, str] | None = None) -> None:  # noqa: D102
        ...


class GaugeLabelLike(Protocol):
    """Interface do label de um Gauge (suporta set)."""

    def set(self, value: float) -> None:  # noqa: D102
        ...


class GaugeLike(Protocol):
    """Interface mínima de um Gauge (retorna um label para set)."""

    def labels(self, **kwargs: str) -> GaugeLabelLike:  # noqa: D102
        ...


class _NoOpCounter:
    """Implementação no-op para Counter."""

    def inc(self, *_args: object, **_kwargs: object) -> None:
        return


class _NoOpHistogram:
    """Implementação no-op para Histogram."""

    def observe(self, *_args: object, **_kwargs: object) -> None:
        return


class _NoOpGauge:
    """Implementação no-op para Gauge com labels()."""

    def labels(self, **_kwargs: str) -> _NoOpGauge:
        return self

    def set(self, *_args: object, **_kwargs: object) -> None:
        return


# Declaração única com fallback no-op
SLOTS_RESERVADOS_TOTAL: CounterLike = _NoOpCounter()
SLOTS_RESERVA_ERROS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CRIADOS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CANCELADOS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_REAGENDADOS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CHECKIN_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CONCLUIDOS_TOTAL: CounterLike = _NoOpCounter()
WAITLIST_INSCRICOES_TOTAL: CounterLike = _NoOpCounter()
WAITLIST_PROMOCOES_TOTAL: CounterLike = _NoOpCounter()
EVENTO_SYNC_TOTAL: CounterLike = _NoOpCounter()
MIRROR_FALHAS_TOTAL: CounterLike = _NoOpCounter()
EVENTO_METADATA_MIGRACOES_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CRIACAO_ERROS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CHECKIN_ERROS_TOTAL: CounterLike = _NoOpCounter()
AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL: CounterLike = _NoOpCounter()
H_CRIA: HistogramLike = _NoOpHistogram()
H_CANCELA: HistogramLike = _NoOpHistogram()
H_REAGENDA: HistogramLike = _NoOpHistogram()
SLOTS_CAP_TOTAL_GAUGE: GaugeLike = _NoOpGauge()
SLOTS_CAP_UTIL_GAUGE: GaugeLike = _NoOpGauge()

try:  # pragma: no cover
    from prometheus_client import Counter, Gauge, Histogram

    _METRICS_ENABLED = True
    SLOTS_RESERVADOS_TOTAL = Counter(
        "ag_slots_reservados_total",
        "Total de reservas de slots via fachada",
    )
    SLOTS_RESERVA_ERROS_TOTAL = Counter(
        "ag_slots_reserva_erros_total",
        "Total de erros em tentativas de reserva de slots",
    )
    AGENDAMENTOS_CRIADOS_TOTAL = Counter(
        "ag_agendamentos_criados_total",
        "Total de agendamentos criados",
    )
    AGENDAMENTOS_CANCELADOS_TOTAL = Counter(
        "ag_agendamentos_cancelados_total",
        "Total de agendamentos cancelados",
    )
    AGENDAMENTOS_REAGENDADOS_TOTAL = Counter(
        "ag_agendamentos_reagendados_total",
        "Total de agendamentos reagendados",
    )
    AGENDAMENTOS_CHECKIN_TOTAL = Counter(
        "ag_agendamentos_checkin_total",
        "Total de check-ins realizados",
    )
    AGENDAMENTOS_CONCLUIDOS_TOTAL = Counter(
        "ag_agendamentos_concluidos_total",
        "Total de agendamentos concluídos",
    )
    WAITLIST_INSCRICOES_TOTAL = Counter(
        "ag_waitlist_inscricoes_total",
        "Total de inscrições em waitlist",
    )
    WAITLIST_PROMOCOES_TOTAL = Counter(
        "ag_waitlist_promocoes_total",
        "Total de promoções automáticas de waitlist",
    )
    EVENTO_SYNC_TOTAL = Counter(
        "ag_evento_sync_total",
        "Total de sincronizações de evento espelho",
    )
    MIRROR_FALHAS_TOTAL = Counter(
        "ag_evento_mirror_falhas_total",
        "Falhas ao criar/atualizar evento espelho",
    )
    EVENTO_METADATA_MIGRACOES_TOTAL = Counter(
        "ag_evento_metadata_migracoes_total",
        "Migrações metadata evento_id -> evento_agenda_id",
    )
    AGENDAMENTOS_CRIACAO_ERROS_TOTAL = Counter(
        "ag_agendamentos_criacao_erros_total",
        "Erros de validação ao criar agendamento",
    )
    AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL = Counter(
        "ag_agendamentos_cancelamento_erros_total",
        "Erros de validação ao cancelar agendamento",
    )
    AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL = Counter(
        "ag_agendamentos_reagendamento_erros_total",
        "Erros de validação ao reagendar agendamento",
    )
    AGENDAMENTOS_CHECKIN_ERROS_TOTAL = Counter(
        "ag_agendamentos_checkin_erros_total",
        "Erros de validação ao realizar checkin",
    )
    AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL = Counter(
        "ag_agendamentos_conclusao_erros_total",
        "Erros de validação ao concluir agendamento",
    )
    H_CRIA = Histogram(
        "ag_agendamento_criacao_latency_seconds",
        "Latência para criação de agendamento",
    )
    H_CANCELA = Histogram(
        "ag_agendamento_cancelamento_latency_seconds",
        "Latência para cancelamento de agendamento",
    )
    H_REAGENDA = Histogram(
        "ag_agendamento_reagendamento_latency_seconds",
        "Latência para reagendamento de agendamento",
    )
    SLOTS_CAP_TOTAL_GAUGE = Gauge(
        "ag_slots_capacidade_total",
        "Capacidade total (janela curta) de slots futuros",
        ["profissional_id"],
    )
    SLOTS_CAP_UTIL_GAUGE = Gauge(
        "ag_slots_capacidade_utilizada",
        "Capacidade utilizada (janela curta) de slots futuros",
        ["profissional_id"],
    )
except ImportError:  # pragma: no cover
    _METRICS_ENABLED = False

# --- Cache leve (slots/disponibilidades) ----------------------------------

_SLOTS_CACHE_VERSION_KEY = "ag_slots_cache_version"


def get_slots_cache_version() -> str:
    """Obtém a versão de cache para slots, criando se ausente (TTL 1 dia)."""
    v = cache.get(_SLOTS_CACHE_VERSION_KEY)
    if not v:
        v = str(time.time())
        with contextlib.suppress(Exception):
            cache.set(_SLOTS_CACHE_VERSION_KEY, v, 86400)  # 1 dia de retenção da versão
    return v


def bump_slots_cache_version() -> None:
    """Avança a versão de cache para invalidação cooperativa."""
    with contextlib.suppress(Exception):
        cache.set(_SLOTS_CACHE_VERSION_KEY, str(time.time()), 86400)


def _update_capacity_gauges(tenant_id: int | None = None) -> None:  # pragma: no cover (simples)
    """Atualiza gauges de capacidade por profissional (janela hoje + amanhã).

    Evita alta cardinalidade: apenas próximos 2 dias e label único (profissional_id).
    Protegido por flag ENABLE_CAPACITY_GAUGES.
    """
    from django.conf import settings as _s  # noqa: PLC0415

    if not getattr(_s, "ENABLE_CAPACITY_GAUGES", False):
        return
    if not _METRICS_ENABLED:
        return
    hoje = timezone.now().date()
    amanha = hoje + timedelta(days=1)
    base = Slot.objects.filter(horario__date__in=[hoje, amanha], ativo=True)
    if tenant_id:
        base = base.filter(tenant_id=tenant_id)
    # agrega por profissional

    agg = base.values("profissional_id").annotate(ct=Sum("capacidade_total"), cu=Sum("capacidade_utilizada"))
    # Zerar antigos? Não - sobrescrevemos apenas presentes. (Profissionais sem slots caem para último valor)
    for row in agg:
        pid = str(row["profissional_id"])
        with contextlib.suppress(Exception):
            SLOTS_CAP_TOTAL_GAUGE.labels(profissional_id=pid).set(row["ct"] or 0)
            SLOTS_CAP_UTIL_GAUGE.labels(profissional_id=pid).set(row["cu"] or 0)


def _map_status_evento(status_agendamento: str) -> str:
    mapa = {
        "PENDENTE": "pendente",
        "CONFIRMADO": "confirmado",
        "EM_ANDAMENTO": "confirmado",  # mantém 'confirmado'
        "CONCLUIDO": "concluido",
        "CANCELADO": "cancelado",
        "REAGENDADO": "confirmado",
        "NO_SHOW": "cancelado",
    }
    return mapa.get(status_agendamento, "pendente")


def _mirror_evento(
    agendamento: Agendamento,
    *,
    criar_se_ausente: bool = True,
) -> None:  # pragma: no cover (feature flag)
    """Cria ou atualiza o Evento espelho quando ENABLE_EVENT_MIRROR=True.

    Usa a mesma chave de metadata dos signals históricos: ``evento_agenda_id``.
    Também migra entradas antigas de ``evento_id`` para ``evento_agenda_id``.
    """
    if not getattr(dj_settings, "ENABLE_EVENT_MIRROR", False):
        return

    try:
        from agenda.models import Evento as _Check  # noqa: PLC0415, F401
    except ImportError:  # pragma: no cover - ausência de app de agenda
        return

    meta = agendamento.metadata if isinstance(agendamento.metadata, dict) else {}
    _migrate_evento_metadata(agendamento, meta)

    evento_any = meta.get("evento_agenda_id")
    evento_id: int | None = evento_any if isinstance(evento_any, int) else None
    titulo_base = f"Agendamento #{getattr(agendamento, 'id', '')}"
    nome_serv = getattr(getattr(agendamento, "servico", None), "nome_servico", None)
    if getattr(agendamento, "servico_id", None) and nome_serv:
        titulo_base += f" - {nome_serv}"

    if not evento_id and criar_se_ausente:
        _criar_evento_espelho(agendamento, meta, titulo_base)
        return

    if evento_id:
        _atualizar_evento_espelho(agendamento, evento_id, criar_se_ausente=criar_se_ausente)
    return


def _migrate_evento_metadata(agendamento: Agendamento, meta: dict[str, Any]) -> None:
    """Migra metadata de 'evento_id' para 'evento_agenda_id' se necessário."""
    if "evento_id" in meta and "evento_agenda_id" not in meta:
        meta["evento_agenda_id"] = meta.pop("evento_id")
        agendamento.metadata = meta
        with contextlib.suppress(Exception):
            agendamento.save(update_fields=["metadata"])
            with contextlib.suppress(Exception):  # pragma: no cover
                EVENTO_METADATA_MIGRACOES_TOTAL.inc()


def _criar_evento_espelho(agendamento: Agendamento, meta: dict[str, Any], titulo_base: str) -> None:
    """Cria Evento espelho e grava o id em metadata (silencioso em falha)."""
    try:
        from agenda.models import Evento  # noqa: PLC0415

        ev = Evento.objects.create(
            tenant=agendamento.tenant,
            titulo=titulo_base,
            descricao="Espelho automático de agendamento",
            data_inicio=agendamento.data_inicio,
            data_fim=agendamento.data_fim,
            status=_map_status_evento(agendamento.status),
            tipo_evento="servico",
            responsavel=agendamento.profissional,
        )
        meta["evento_agenda_id"] = getattr(ev, "id", None)
        agendamento.metadata = meta
        agendamento.save(update_fields=["metadata"])
    except Exception:  # noqa: BLE001 - tolera ausência da app; pragma: no cover
        with contextlib.suppress(Exception):
            MIRROR_FALHAS_TOTAL.inc()


def _atualizar_evento_espelho(
    agendamento: Agendamento,
    evento_id: int,
    *,
    criar_se_ausente: bool,
) -> None:
    """Atualiza Evento espelho existente ou cria se ausente quando permitido."""
    try:
        from agenda.models import Evento  # noqa: PLC0415

        ev = Evento.objects.filter(id=evento_id, tenant=agendamento.tenant).first()
        if not ev and criar_se_ausente:
            _mirror_evento(agendamento, criar_se_ausente=True)
            return
        if ev:
            alterado = False
            if ev.data_inicio != agendamento.data_inicio:
                ev.data_inicio = agendamento.data_inicio
                alterado = True
            if ev.data_fim != agendamento.data_fim:
                ev.data_fim = agendamento.data_fim
                alterado = True
            novo_status = _map_status_evento(agendamento.status)
            if ev.status != novo_status:
                ev.status = novo_status
                alterado = True
            if alterado:
                ev.save(update_fields=["data_inicio", "data_fim", "status", "data_atualizacao"])
    except Exception:  # noqa: BLE001 - tolera ausência da app; pragma: no cover
        with contextlib.suppress(Exception):
            MIRROR_FALHAS_TOTAL.inc()


class SlotService:
    """Serviços de manipulação de slots (reserva e geração)."""

    @staticmethod
    def reservar(slot: Slot, quantidade: int = 1) -> Slot:
        """Reserva atomicamente capacidade de um slot e atualiza gauges/cache."""
        if quantidade < 1:
            msg = "Quantidade inválida"
            raise ValueError(msg)
        with transaction.atomic():
            locked = Slot.objects.select_for_update().get(pk=slot.pk)
            if not locked.disponivel:
                msg = "Slot indisponível"
                raise ValueError(msg)
            from django.conf import settings as _s  # noqa: PLC0415

            limite = locked.capacidade_total
            if getattr(_s, "ENABLE_CONTROLLED_OVERBOOK", False):
                limite += getattr(_s, "AGENDAMENTOS_OVERBOOK_EXTRA", 1)
            if locked.capacidade_utilizada + quantidade > limite:
                msg = "Slot indisponível"
                raise ValueError(msg)
            locked.capacidade_utilizada += quantidade
            locked.save(update_fields=["capacidade_utilizada"])
        slot.refresh_from_db(fields=["capacidade_utilizada"])
        bump_slots_cache_version()
        _update_capacity_gauges(getattr(slot, "tenant_id", None))
        return slot

    @staticmethod
    def gerar_slots(disponibilidade: Disponibilidade) -> tuple[int, int]:
        """Gera slots discretos; idempotente. Retorna (criados, existentes)."""
        created = 0
        existentes = 0
        data = disponibilidade.data
        tz = timezone.get_current_timezone()
        inicio_dt = timezone.make_aware(datetime.combine(data, disponibilidade.hora_inicio), tz)
        fim_dt = timezone.make_aware(datetime.combine(data, disponibilidade.hora_fim), tz)
        delta = timedelta(minutes=disponibilidade.duracao_slot_minutos)
        atual = inicio_dt
        while atual < fim_dt:
            slot, created_flag = Slot.objects.get_or_create(
                tenant=disponibilidade.tenant,
                disponibilidade=disponibilidade,
                profissional=disponibilidade.profissional,
                horario=atual,
                defaults={
                    "capacidade_total": disponibilidade.capacidade_por_slot,
                    "capacidade_utilizada": 0,
                    "ativo": True,
                },
            )
            if created_flag:
                created += 1
            else:
                existentes += 1
            atual += delta
        bump_slots_cache_version()
        _update_capacity_gauges(getattr(disponibilidade, "tenant_id", None))
        return created, existentes


class AgendamentoService:
    """Serviços de criação e alteração de agendamentos."""

    @staticmethod
    def criar(  # noqa: PLR0913
        *,
        tenant: object,
        cliente: object,
        profissional: object,
        data_inicio: datetime,
        data_fim: datetime | None = None,
        origem: str,
        slot: Slot | None = None,
        tipo_servico: object | None = None,
        servico: object | None = None,
        metadata: dict[str, Any] | None = None,
        user: object | None = None,
    ) -> Agendamento:
        """Cria um agendamento aplicando validações e auditoria."""
        # Carregar servico (se informado) e aplicar regras antes do conflito manual
        try:
            return AgendamentoService._criar_impl(
                tenant=tenant,
                cliente=cliente,
                profissional=profissional,
                data_inicio=data_inicio,
                data_fim=data_fim,
                origem=origem,
                slot=slot,
                tipo_servico=tipo_servico,
                servico=servico,
                metadata=metadata,
                user=user,
            )
        except ValueError:
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CRIACAO_ERROS_TOTAL.inc()
            raise

    @staticmethod
    def _criar_impl(  # noqa: C901, PLR0913, PLR0912, PLR0915
        *,
        tenant: object,
        cliente: object,
        profissional: object,
        data_inicio: datetime,
        data_fim: datetime | None = None,
        origem: str,
        slot: Slot | None = None,
        tipo_servico: object | None = None,
        servico: object | None = None,
        metadata: dict[str, Any] | None = None,
        user: object | None = None,
    ) -> Agendamento:
        # Evita aviso de parâmetro não utilizado mantido por compatibilidade
        del tipo_servico
        from servicos.models import Servico as Serv  # noqa: PLC0415

        proc_obj = None
        # Flag para exigir servico

        require_serv = getattr(dj_settings, "REQUIRE_SERVICO", False)
        if require_serv and not servico:
            msg = "Serviço obrigatório (REQUIRE_SERVICO habilitado)"
            raise ValueError(msg)
        if servico:
            if isinstance(servico, int | str):
                try:
                    proc_obj = Serv.objects.get(id=servico, tenant=tenant, ativo=True, is_clinical=True)
                except Serv.DoesNotExist:
                    msg = "Serviço inválido"
                    raise ValueError(msg) from None
            else:
                proc_obj = servico
            # Perfil clínico associado (campos específicos)
            perfil_clinico = getattr(proc_obj, "perfil_clinico", None)
            # Validação de competência Profissional x Serviço (feature flag)
            if getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
                from agendamentos.models import ProfissionalProcedimento  # noqa: PLC0415

                ok = ProfissionalProcedimento.objects.filter(
                    tenant=tenant,
                    profissional=profissional,
                    servico=proc_obj,
                    ativo=True,
                ).exists()
                if not ok:
                    msg = "Profissional não habilitado para este serviço"
                    raise ValueError(msg)
            # Intervalo mínimo entre sessões concluídas
            ultimo = (
                Agendamento.objects.filter(tenant=tenant, cliente=cliente, servico=proc_obj, status="CONCLUIDO")
                .order_by("-data_inicio")
                .first()
            )
            if ultimo:
                delta_dias = (data_inicio.date() - ultimo.data_inicio.date()).days
                intervalo_min = getattr(perfil_clinico, "intervalo_minimo_sessoes", 0) if perfil_clinico else 0
                if delta_dias < intervalo_min:
                    msg = "Intervalo mínimo entre sessões não atendido"
                    raise ValueError(msg)
            # Duração automática se não fornecida
            if data_fim is None:
                dur_est = getattr(perfil_clinico, "duracao_estimada", None)
                if dur_est:
                    data_fim = data_inicio + dur_est
        # Conflito manual somente após definir data_fim
        if not slot:
            if not data_fim:
                msg = "data_fim obrigatório"
                raise ValueError(msg)
            conflito = (
                Agendamento.objects.filter(
                    tenant=tenant,
                    profissional=profissional,
                    status__in=["PENDENTE", "CONFIRMADO", "EM_ANDAMENTO"],
                )
                .filter(Q(data_inicio__lt=data_fim) & Q(data_fim__gt=data_inicio))
                .exists()
            )
            if conflito:
                msg = "Conflito de horário para o profissional (agendamento manual)"
                raise ValueError(msg)
        if not data_fim:
            msg = "data_fim obrigatório"
            raise ValueError(msg)
        if data_fim <= data_inicio:
            msg = "data_fim deve ser maior que data_inicio"
            raise ValueError(msg)
        if slot and proc_obj:
            # Heurística simples de incompatibilidade (slot único curto vs duração longa)
            one_hour_seconds = 3600
            if (data_fim - data_inicio).total_seconds() > one_hour_seconds:  # >1h
                msg = "Duração do serviço maior que o slot disponível"
                raise ValueError(msg)
        with transaction.atomic():
            if slot:
                SlotService.reservar(slot)
            ag = Agendamento.objects.create(
                tenant=tenant,
                cliente=cliente,
                profissional=profissional,
                slot=slot,
                data_inicio=data_inicio,
                data_fim=data_fim,
                origem=origem,
                # tipo_servico legado removido
                servico=proc_obj,
                metadata={**(metadata or {}), **({"manual_sem_slot": True} if not slot else {})},
                status="CONFIRMADO" if origem in ["OPERADOR", "PROFISSIONAL"] else "PENDENTE",
            )
            if proc_obj:
                perfil_clinico = getattr(proc_obj, "perfil_clinico", None)
                if perfil_clinico:
                    pendencias = []
                    if getattr(perfil_clinico, "requer_anamnese", False):
                        pendencias.append("anamnese")
                    if getattr(perfil_clinico, "requer_termo_consentimento", False):
                        pendencias.append("termo")
                    if pendencias:
                        ag.metadata["pendencias"] = pendencias
                        ag.save(update_fields=["metadata"])
            diff = {}
            sid = getattr(ag, "servico_id", None)
            if sid:
                diff["servico_id"] = sid
            diff["data_inicio"] = ag.data_inicio.isoformat()
            diff["data_fim"] = ag.data_fim.isoformat()
            diff["profissional_id"] = getattr(ag, "profissional_id", None)
            AuditoriaAgendamento.objects.create(
                agendamento=ag,
                user=user,
                tipo_evento="CRIACAO",
                para_status=ag.status,
                diff=diff or None,
            )
            nome_proc = getattr(proc_obj, "nome", None) or "Serviço"
            notificar_profissional_e_clientes(
                agendamento=ag,
                titulo_prof=f"Novo Agendamento - {nome_proc}",
                msg_prof=(
                    f"Agendamento #{getattr(ag, 'id', '')} ({nome_proc}) criado para {ag.cliente} em {ag.data_inicio}."
                ),
                titulo_cli=f"Seu Agendamento - {nome_proc}",
                msg_cli=(f"Seu agendamento #{getattr(ag, 'id', '')} ({nome_proc}) foi criado para {ag.data_inicio}."),
                tipo="info",
            )
            # Mirror de evento (fora do bloco crítico de criação de auditoria já executado)
            _mirror_evento(ag)
            return ag

    @staticmethod
    def _validar_cancelamento_cliente(agendamento: Agendamento) -> None:
        if agendamento.origem != "CLIENTE":
            return
        from django.utils import timezone  # noqa: PLC0415

        antecedencia = (agendamento.data_inicio - timezone.now()).total_seconds() / 60.0
        if antecedencia < settings.AGENDAMENTOS_CANCEL_ANTECEDENCIA_MINUTOS:
            msg = "Cancelamento não permitido dentro da antecedência mínima"
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL.inc()
            raise ValueError(msg)

    @staticmethod
    def _promover_waitlist(locked_slot: Slot, user: object | None, agendamento_cancelado_id: int) -> None:
        from django.conf import settings as _s  # noqa: PLC0415

        if not getattr(_s, "ENABLE_WAITLIST", False):
            return
        limite = locked_slot.capacidade_total
        if getattr(_s, "ENABLE_CONTROLLED_OVERBOOK", False):
            limite += getattr(_s, "AGENDAMENTOS_OVERBOOK_EXTRA", 1)
        if locked_slot.capacidade_utilizada >= limite:
            return
        wl_manager = getattr(locked_slot, "waitlist", None)
        if wl_manager:
            base_qs = wl_manager.select_for_update()
        else:
            base_qs = WaitlistEntry.objects.select_for_update().filter(slot=locked_slot)
        entry = base_qs.filter(status="ATIVO").order_by("prioridade", "created_at").first()
        if not entry:
            return
        from datetime import timedelta as _td  # noqa: PLC0415

        inicio = locked_slot.horario
        fim = inicio + _td(minutes=locked_slot.disponibilidade.duracao_slot_minutos)
        novo_ag = Agendamento.objects.create(
            tenant=locked_slot.tenant,
            cliente=entry.cliente,
            profissional=locked_slot.profissional,
            slot=locked_slot,
            data_inicio=inicio,
            data_fim=fim,
            origem="SISTEMA",
            status="PENDENTE",
            metadata={"waitlist_promocao": True},
        )
        entry.status = "PROMOVIDO"
        entry.save(update_fields=["status"])
        AuditoriaAgendamento.objects.create(
            agendamento=novo_ag,
            user=user,
            tipo_evento="WAITLIST_PROMOCAO",
            de_status=None,
            para_status="PENDENTE",
            motivo=f"Promoção automática após cancelamento #{agendamento_cancelado_id}",
        )
        with contextlib.suppress(Exception):
            WAITLIST_PROMOCOES_TOTAL.inc()
        bump_slots_cache_version()
        _update_capacity_gauges(getattr(locked_slot, "tenant_id", None))
        notificar_profissional_e_clientes(
            agendamento=novo_ag,
            titulo_prof="Waitlist Promovida",
            msg_prof=f"Cliente {entry.cliente} promovido do waitlist para slot {locked_slot.horario}.",
            titulo_cli="Sua vaga ficou disponível",
            msg_cli=f"Seu agendamento foi criado a partir da lista de espera para {locked_slot.horario}.",
            tipo="info",
        )

    @staticmethod
    def _liberar_slot_e_promover_waitlist(agendamento: Agendamento, user: object | None) -> None:
        if not agendamento.slot:
            return
        with transaction.atomic():
            locked = Slot.objects.select_for_update().get(pk=getattr(agendamento, "slot_id", None))
            if locked.capacidade_utilizada > 0:
                locked.capacidade_utilizada -= 1
                locked.save(update_fields=["capacidade_utilizada"])
                bump_slots_cache_version()
                _update_capacity_gauges(getattr(locked, "tenant_id", None))
            AgendamentoService._promover_waitlist(locked, user, getattr(agendamento, "id", 0))

    @staticmethod
    def _cancelar_logica(agendamento: Agendamento, motivo: str, user: object | None) -> None:
        """Lógica interna de cancelamento, separada para reduzir complexidade."""
        # Validações
        if agendamento.status in {"CANCELADO", "CONCLUIDO", "REMARCADO"}:
            msg = f"Agendamento já está no estado final '{agendamento.status}'"
            raise ValueError(msg)

        if getattr(user, "is_cliente", False):
            AgendamentoService._validar_cancelamento_cliente(agendamento)

        # Lógica de cancelamento
        de_status = agendamento.status
        agendamento.status = "CANCELADO"
        agendamento.cancelado_em = timezone.now()
        agendamento.cancelado_por = user
        agendamento.motivo_cancelamento = motivo
        agendamento.save(
            update_fields=[
                "status",
                "cancelado_em",
                "cancelado_por",
                "motivo_cancelamento",
            ],
        )

        # Auditoria
        AuditoriaAgendamento.objects.create(
            agendamento=agendamento,
            user=user,
            tipo_evento="CANCELAMENTO",
            de_status=de_status,
            para_status="CANCELADO",
            motivo=motivo,
        )

        # Métricas
        with contextlib.suppress(Exception):
            AGENDAMENTOS_CANCELADOS_TOTAL.inc()

        # Liberação de vaga e promoção de waitlist
        AgendamentoService._liberar_slot_e_promover_waitlist(agendamento, user)

        # Notificações
        if getattr(dj_settings, "ENABLE_NOTIFICATIONS", True):
            notificar_profissional_e_clientes(
                agendamento=agendamento,
                titulo_prof="Agendamento Cancelado",
                msg_prof=f"Agendamento de {agendamento.cliente} em {agendamento.data_inicio_fmt} foi cancelado.",
                titulo_cli="Seu agendamento foi cancelado",
                msg_cli=f"Seu agendamento em {agendamento.data_inicio_fmt} foi cancelado.",
                tipo="warning",
            )

    @staticmethod
    def cancelar(
        agendamento: Agendamento,
        *,
        motivo: str,
        user: object | None = None,
    ) -> Agendamento:
        """Cancela um agendamento, atualiza status, audita e notifica.

        Args:
            agendamento: A instância do agendamento a ser cancelado.
            motivo: A razão do cancelamento.
            user: O usuário que está realizando o cancelamento.

        Returns:
            A instância do agendamento atualizada.

        Raises:
            ValueError: Se o agendamento não puder ser cancelado.

        """
        AgendamentoService._cancelar_logica(agendamento, motivo, user)
        return agendamento

    @staticmethod
    def reagendar(  # noqa: C901, PLR0913, PLR0912, PLR0915
        agendamento: Agendamento,
        *,
        novo_slot: Slot | None = None,
        nova_data_inicio: datetime | None = None,
        nova_data_fim: datetime | None = None,
        user: object | None = None,
        motivo: str | None = None,
    ) -> Agendamento:
        """Reagenda um agendamento criando um novo registro encadeado."""
        if agendamento.status == "CANCELADO":
            msg = "Não reagendar agendamento cancelado"
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL.inc()
            raise ValueError(msg)
        cadeia = 0
        ref = agendamento
        while getattr(ref, "referencia_anterior_id", None) and cadeia <= settings.AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX:
            cadeia += 1
            next_ref = getattr(ref, "referencia_anterior", None)
            if next_ref is None:
                break
            ref = next_ref
        if cadeia >= settings.AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX:
            msg = "Limite de reagendamentos excedido"
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL.inc()
            raise ValueError(msg)
        AgendamentoService.cancelar(agendamento, motivo=(motivo or "Reagendado"), user=user)
        if novo_slot:
            SlotService.reservar(novo_slot)
            nova_data_inicio = novo_slot.horario
            if not nova_data_fim:
                proc = getattr(agendamento, "servico", None)
                if proc and getattr(proc, "duracao_estimada", None):
                    nova_data_fim = nova_data_inicio + proc.duracao_estimada
                else:
                    disp = getattr(novo_slot, "disponibilidade", None)
                    if disp and getattr(disp, "duracao_slot_minutos", None):
                        from datetime import timedelta as _td  # noqa: PLC0415

                        nova_data_fim = nova_data_inicio + _td(minutes=disp.duracao_slot_minutos)
        if not nova_data_inicio or not nova_data_fim:
            msg = "Datas obrigatórias para novo agendamento"
            raise ValueError(msg)
        antes_proc = getattr(agendamento, "servico_id", None)
        antes_inicio = agendamento.data_inicio
        antes_fim = agendamento.data_fim
        antes_prof = getattr(agendamento, "profissional_id", None)
        novo = Agendamento.objects.create(
            tenant=agendamento.tenant,
            cliente=agendamento.cliente,
            profissional=agendamento.profissional if not novo_slot else novo_slot.profissional,
            slot=novo_slot,
            data_inicio=nova_data_inicio,
            data_fim=nova_data_fim,
            origem=agendamento.origem,
            servico=agendamento.servico,
            metadata=agendamento.metadata,
            referencia_anterior=agendamento,
            status="CONFIRMADO",
        )
        diff: dict[str, Any] = {}
        if antes_proc != getattr(novo, "servico_id", None):
            diff["servico_de"] = antes_proc
            diff["servico_para"] = getattr(novo, "servico_id", None)
        if antes_inicio != novo.data_inicio:
            diff["data_inicio_de"] = antes_inicio.isoformat()
            diff["data_inicio_para"] = novo.data_inicio.isoformat()
        if antes_fim != novo.data_fim:
            diff["data_fim_de"] = antes_fim.isoformat()
            diff["data_fim_para"] = novo.data_fim.isoformat()
        if antes_prof != getattr(novo, "profissional_id", None):
            diff["profissional_de"] = antes_prof
            diff["profissional_para"] = getattr(novo, "profissional_id", None)
        AuditoriaAgendamento.objects.create(
            agendamento=novo,
            user=user,
            tipo_evento="REAGENDAMENTO",
            de_status=None,
            para_status="CONFIRMADO",
            motivo=motivo,
            diff=diff or None,
        )
        nome_proc = getattr(novo.servico, "nome_servico", None) or "Serviço"
        notificar_profissional_e_clientes(
            agendamento=novo,
            titulo_prof=f"Agendamento Reagendado - {nome_proc}",
            msg_prof=(
                f"Agendamento #{getattr(novo, 'id', '')} ({nome_proc}) reagendado "
                f"(anterior #{getattr(agendamento, 'id', '')})."
            ),
            titulo_cli=f"Agendamento Reagendado - {nome_proc}",
            msg_cli=(
                f"Seu agendamento ({nome_proc}) foi reagendado para {novo.data_inicio}. "
                f"(original #{getattr(agendamento, 'id', '')})"
            ),
            tipo="info",
        )
        _mirror_evento(novo)
        # Se mudou slot (novo_slot), capacidade já foi ajustada -> gauges/cache atualizados pelas operações anteriores
        return novo

    @staticmethod
    def checkin(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Realiza check-in alterando status para EM_ANDAMENTO."""
        if agendamento.status != "CONFIRMADO":
            msg = "Só é possível dar check-in em agendamentos CONFIRMADO"
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CHECKIN_ERROS_TOTAL.inc()
            raise ValueError(msg)
        pendencias = (agendamento.metadata or {}).get("pendencias") if isinstance(agendamento.metadata, dict) else None
        if pendencias:
            msg = "Pendências clínicas não resolvidas: " + ", ".join(pendencias)
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CHECKIN_ERROS_TOTAL.inc()
            raise ValueError(msg)
        agendamento.status = "EM_ANDAMENTO"
        agendamento.save(update_fields=["status", "updated_at"])
        AuditoriaAgendamento.objects.create(
            agendamento=agendamento,
            user=user,
            tipo_evento="CHECKIN",
            de_status="CONFIRMADO",
            para_status="EM_ANDAMENTO",
        )
        _mirror_evento(agendamento, criar_se_ausente=False)
        return agendamento

    @staticmethod
    def concluir(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Conclui um agendamento elegível (CONFIRMADO/EM_ANDAMENTO)."""
        if agendamento.status not in ["EM_ANDAMENTO", "CONFIRMADO"]:
            msg = "Conclusão só permitida para EM_ANDAMENTO ou CONFIRMADO"
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL.inc()
            raise ValueError(msg)
        anterior = agendamento.status
        agendamento.status = "CONCLUIDO"
        agendamento.save(update_fields=["status", "updated_at"])
        AuditoriaAgendamento.objects.create(
            agendamento=agendamento,
            user=user,
            tipo_evento="CONCLUSAO",
            de_status=anterior,
            para_status="CONCLUIDO",
        )
        _mirror_evento(agendamento, criar_se_ausente=False)
        return agendamento

    @staticmethod
    def resolver_pendencias(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Remove pendências clínicas quando presentes e audita a ação."""
        if not isinstance(agendamento.metadata, dict):
            return agendamento
        pendencias = agendamento.metadata.pop("pendencias", None)
        if pendencias:
            agendamento.save(update_fields=["metadata"])
            AuditoriaAgendamento.objects.create(
                agendamento=agendamento,
                user=user,
                tipo_evento="PENDENCIAS_RESOLVIDAS",
                diff={"pendencias_removidas": pendencias},
            )
        return agendamento

    @staticmethod
    def inscrever_waitlist(slot: Slot, *, cliente: object, prioridade: int = 100) -> WaitlistEntry:
        """Inscreve um cliente na waitlist (idempotente por slot/cliente)."""
        from django.conf import settings  # noqa: PLC0415

        if not getattr(settings, "ENABLE_WAITLIST", False):
            msg = "Waitlist desabilitada"
            raise ValueError(msg)
        obj, created = WaitlistEntry.objects.get_or_create(
            tenant=slot.tenant,
            slot=slot,
            cliente=cliente,
            defaults={"prioridade": prioridade},
        )
        if not created:
            obj.prioridade = prioridade
            obj.save(update_fields=["prioridade"])
        return obj


class SchedulingService:
    """Fachada de alto nível para operações de agenda."""

    """Fachada de alto nível (compat / orquestração) para operações de agenda.

    Mantém interface única caso camadas externas (ex: portal, integrações) desejem
    reduzir acoplamento aos serviços internos. Todos os métodos delegam para
    SlotService / AgendamentoService sem alterar regras de negócio.

    Justificativas:
    - Facilita substituição futura de implementação (ex: mover para microserviço).
    - Ponto central para interceptar métricas, tracing, caching ou políticas.
    - Permite evoluir atomicamente sem tocar consumidores existentes.
    """

    # Slots ---------------------------------------------------------------
    @staticmethod
    def gerar_slots(disponibilidade: Disponibilidade) -> tuple[int, int]:
        """Gera slots e retorna contagem (criados, existentes)."""
        return SlotService.gerar_slots(disponibilidade)

    @staticmethod
    def reservar_slot(slot: Slot, quantidade: int = 1) -> Slot:
        """Reserva capacidade no slot, incrementando métricas."""
        try:
            slot = SlotService.reservar(slot, quantidade=quantidade)
        except Exception:
            with contextlib.suppress(Exception):  # pragma: no cover
                SLOTS_RESERVA_ERROS_TOTAL.inc()
            raise
        else:
            with contextlib.suppress(Exception):  # pragma: no cover
                SLOTS_RESERVADOS_TOTAL.inc()
            return slot

    # Agendamentos --------------------------------------------------------
    @staticmethod
    def criar_agendamento(  # noqa: PLR0913
        *,
        tenant: object,
        cliente: object,
        profissional: object,
        data_inicio: datetime,
        data_fim: datetime | None = None,
        origem: str,
        slot: Slot | None = None,
        tipo_servico: object | None = None,
        servico: object | None = None,
        metadata: dict[str, Any] | None = None,
        user: object | None = None,
    ) -> Agendamento:
        """Cria um agendamento delegando ao serviço interno."""
        t0 = monotonic()
        ag = AgendamentoService.criar(
            tenant=tenant,
            cliente=cliente,
            profissional=profissional,
            data_inicio=data_inicio,
            data_fim=data_fim,
            origem=origem,
            slot=slot,
            tipo_servico=tipo_servico,
            servico=servico,
            metadata=metadata,
            user=user,
        )
        dur = monotonic() - t0
        with contextlib.suppress(Exception):  # pragma: no cover
            AGENDAMENTOS_CRIADOS_TOTAL.inc()
            H_CRIA.observe(dur)
        return ag

    @staticmethod
    def cancelar_agendamento(
        agendamento: Agendamento,
        *,
        motivo: str,
        user: object | None = None,
    ) -> Agendamento:
        """Cancela o agendamento e registra métricas de latência."""
        t0 = monotonic()
        status_antes = agendamento.status
        ag = AgendamentoService.cancelar(agendamento, motivo=motivo, user=user)
        dur = monotonic() - t0
        if status_antes != "CANCELADO" and ag.status == "CANCELADO":
            with contextlib.suppress(Exception):  # pragma: no cover
                AGENDAMENTOS_CANCELADOS_TOTAL.inc()
                H_CANCELA.observe(dur)
        return ag

    @staticmethod
    def reagendar_agendamento(  # noqa: PLR0913
        agendamento: Agendamento,
        *,
        novo_slot: Slot | None = None,
        nova_data_inicio: datetime | None = None,
        nova_data_fim: datetime | None = None,
        user: object | None = None,
        motivo: str | None = None,
    ) -> Agendamento:
        """Reagenda criando um novo registro e mede latência."""
        t0 = monotonic()
        novo = AgendamentoService.reagendar(
            agendamento,
            novo_slot=novo_slot,
            nova_data_inicio=nova_data_inicio,
            nova_data_fim=nova_data_fim,
            user=user,
            motivo=motivo,
        )
        dur = monotonic() - t0
        with contextlib.suppress(Exception):  # pragma: no cover
            AGENDAMENTOS_REAGENDADOS_TOTAL.inc()
            H_REAGENDA.observe(dur)
        return novo

    @staticmethod
    def checkin(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Delegação para check-in com incremento de métrica."""
        ag = AgendamentoService.checkin(agendamento, user=user)
        with contextlib.suppress(Exception):  # pragma: no cover
            AGENDAMENTOS_CHECKIN_TOTAL.inc()
        return ag

    @staticmethod
    def concluir(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Delegação para conclusão com incremento de métrica."""
        ag = AgendamentoService.concluir(agendamento, user=user)
        with contextlib.suppress(Exception):  # pragma: no cover
            AGENDAMENTOS_CONCLUIDOS_TOTAL.inc()
        return ag

    @staticmethod
    def resolver_pendencias(agendamento: Agendamento, *, user: object | None = None) -> Agendamento:
        """Resolve pendências clínicas, se existirem."""
        return AgendamentoService.resolver_pendencias(agendamento, user=user)

    @staticmethod
    def inscrever_waitlist(slot: Slot, *, cliente: object, prioridade: int = 100) -> WaitlistEntry:
        """Inscreve cliente na waitlist e incrementa métrica."""
        obj = AgendamentoService.inscrever_waitlist(slot, cliente=cliente, prioridade=prioridade)
        with contextlib.suppress(Exception):  # pragma: no cover
            WAITLIST_INSCRICOES_TOTAL.inc()
        return obj

    @staticmethod
    def sync_evento(agendamento: Agendamento) -> int | None:
        """Força sincronização do evento espelho se flag habilitada.

        Retorna o id do evento (ou None se desabilitado/não criado).
        """
        _mirror_evento(agendamento, criar_se_ausente=True)
        with contextlib.suppress(Exception):  # pragma: no cover
            EVENTO_SYNC_TOTAL.inc()
        # Recarrega metadata atual (pode ter sido alterada por _mirror_evento)
        agendamento.refresh_from_db(fields=["metadata"])
        meta = agendamento.metadata if isinstance(agendamento.metadata, dict) else {}
        if "evento_id" in meta:
            # Se ainda não existe chave nova, copia o valor
            if "evento_agenda_id" not in meta:
                meta["evento_agenda_id"] = meta["evento_id"]
            # Remove sempre a chave legado para evitar duplicidade
            meta.pop("evento_id", None)
            with contextlib.suppress(Exception):
                agendamento.metadata = meta
                agendamento.save(update_fields=["metadata"])
        return meta.get("evento_agenda_id")

    # Alias curtos (legado)
    criar = criar_agendamento
    cancelar = cancelar_agendamento
    reagendar = reagendar_agendamento

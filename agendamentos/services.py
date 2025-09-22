from datetime import datetime, timedelta

from django.conf import settings
from django.conf import settings as dj_settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Agendamento, AuditoriaAgendamento, Disponibilidade, Slot, WaitlistEntry
from .utils import notificar_profissional_e_clientes

# Métricas Prometheus (counters) - opcionais, só incrementam se biblioteca disponível
try:  # pragma: no cover
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore

    _METRICS_ENABLED = True
except Exception:  # pragma: no cover
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    _METRICS_ENABLED = False

if _METRICS_ENABLED:  # pragma: no cover
    SLOTS_RESERVADOS_TOTAL = Counter("ag_slots_reservados_total", "Total de reservas de slots via fachada")
    SLOTS_RESERVA_ERROS_TOTAL = Counter(
        "ag_slots_reserva_erros_total", "Total de erros em tentativas de reserva de slots"
    )
    AGENDAMENTOS_CRIADOS_TOTAL = Counter("ag_agendamentos_criados_total", "Total de agendamentos criados")
    AGENDAMENTOS_CANCELADOS_TOTAL = Counter("ag_agendamentos_cancelados_total", "Total de agendamentos cancelados")
    AGENDAMENTOS_REAGENDADOS_TOTAL = Counter("ag_agendamentos_reagendados_total", "Total de agendamentos reagendados")
    AGENDAMENTOS_CHECKIN_TOTAL = Counter("ag_agendamentos_checkin_total", "Total de check-ins realizados")
    AGENDAMENTOS_CONCLUIDOS_TOTAL = Counter("ag_agendamentos_concluidos_total", "Total de agendamentos concluídos")
    WAITLIST_INSCRICOES_TOTAL = Counter("ag_waitlist_inscricoes_total", "Total de inscrições em waitlist")
    WAITLIST_PROMOCOES_TOTAL = Counter("ag_waitlist_promocoes_total", "Total de promoções automáticas de waitlist")
    EVENTO_SYNC_TOTAL = Counter("ag_evento_sync_total", "Total de sincronizações de evento espelho")
    MIRROR_FALHAS_TOTAL = Counter("ag_evento_mirror_falhas_total", "Falhas ao criar/atualizar evento espelho")
    EVENTO_METADATA_MIGRACOES_TOTAL = Counter(
        "ag_evento_metadata_migracoes_total", "Migrações metadata evento_id -> evento_agenda_id"
    )
    AGENDAMENTOS_CRIACAO_ERROS_TOTAL = Counter(
        "ag_agendamentos_criacao_erros_total", "Erros de validação ao criar agendamento"
    )
    AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL = Counter(
        "ag_agendamentos_cancelamento_erros_total", "Erros de validação ao cancelar agendamento"
    )
    AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL = Counter(
        "ag_agendamentos_reagendamento_erros_total", "Erros de validação ao reagendar agendamento"
    )
    AGENDAMENTOS_CHECKIN_ERROS_TOTAL = Counter(
        "ag_agendamentos_checkin_erros_total", "Erros de validação ao realizar checkin"
    )
    AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL = Counter(
        "ag_agendamentos_conclusao_erros_total", "Erros de validação ao concluir agendamento"
    )
    # Histogramas simples de latência (segundos)
    H_CRIA = Histogram("ag_agendamento_criacao_latency_seconds", "Latência para criação de agendamento")
    H_CANCELA = Histogram("ag_agendamento_cancelamento_latency_seconds", "Latência para cancelamento de agendamento")
    H_REAGENDA = Histogram("ag_agendamento_reagendamento_latency_seconds", "Latência para reagendamento de agendamento")
    # Gauges (cardinalidade controlada por profissional) – habilitados só se flag ENABLE_CAPACITY_GAUGES
    SLOTS_CAP_TOTAL_GAUGE = Gauge(
        "ag_slots_capacidade_total", "Capacidade total (janela curta) de slots futuros", ["profissional_id"]
    )
    SLOTS_CAP_UTIL_GAUGE = Gauge(
        "ag_slots_capacidade_utilizada", "Capacidade utilizada (janela curta) de slots futuros", ["profissional_id"]
    )
else:  # Fallbacks no-op

    class _NoOp:
        def inc(self, *_args, **_kwargs):
            return None

        def observe(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    SLOTS_RESERVADOS_TOTAL = SLOTS_RESERVA_ERROS_TOTAL = AGENDAMENTOS_CRIADOS_TOTAL = AGENDAMENTOS_CANCELADOS_TOTAL = (
        AGENDAMENTOS_REAGENDADOS_TOTAL
    ) = AGENDAMENTOS_CHECKIN_TOTAL = AGENDAMENTOS_CONCLUIDOS_TOTAL = WAITLIST_INSCRICOES_TOTAL = (
        WAITLIST_PROMOCOES_TOTAL
    ) = EVENTO_SYNC_TOTAL = MIRROR_FALHAS_TOTAL = H_CRIA = H_CANCELA = H_REAGENDA = EVENTO_METADATA_MIGRACOES_TOTAL = (
        SLOTS_CAP_TOTAL_GAUGE
    ) = SLOTS_CAP_UTIL_GAUGE = AGENDAMENTOS_CRIACAO_ERROS_TOTAL = AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL = (
        AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL
    ) = AGENDAMENTOS_CHECKIN_ERROS_TOTAL = AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL = _NoOp()

# --- Cache leve (slots/disponibilidades) ----------------------------------
import contextlib
import time

from django.core.cache import cache

_SLOTS_CACHE_VERSION_KEY = "ag_slots_cache_version"


def get_slots_cache_version():
    v = cache.get(_SLOTS_CACHE_VERSION_KEY)
    if not v:
        v = str(time.time())
        try:
            cache.set(_SLOTS_CACHE_VERSION_KEY, v, 86400)  # 1 dia de retenção da versão
        except Exception:
            pass
    return v


def bump_slots_cache_version():
    with contextlib.suppress(Exception):
        cache.set(_SLOTS_CACHE_VERSION_KEY, str(time.time()), 86400)


def _update_capacity_gauges(tenant_id=None):  # pragma: no cover (simples)
    """Atualiza gauges de capacidade por profissional (janela hoje + amanhã).
    Evita alta cardinalidade: apenas próximos 2 dias e label único (profissional_id).
    Protegido por flag ENABLE_CAPACITY_GAUGES.
    """
    from django.conf import settings as _s

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
    from django.db.models import Sum

    agg = base.values("profissional_id").annotate(ct=Sum("capacidade_total"), cu=Sum("capacidade_utilizada"))
    # Zerar antigos? Não – sobrescrevemos apenas presentes. (Profissionais sem slots caem para último valor)
    for row in agg:
        pid = str(row["profissional_id"])
        try:
            SLOTS_CAP_TOTAL_GAUGE.labels(profissional_id=pid).set(row["ct"] or 0)
            SLOTS_CAP_UTIL_GAUGE.labels(profissional_id=pid).set(row["cu"] or 0)
        except Exception:
            pass


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


def _mirror_evento(agendamento: Agendamento, *, criar_se_ausente=True):  # pragma: no cover (feature flag)
    """Cria ou atualiza um Evento espelho quando ENABLE_EVENT_MIRROR=True.
    Usa a mesma chave de metadata já utilizada pelos signals históricos: 'evento_agenda_id'.
    Mantém compatibilidade com versões intermediárias que gravaram 'evento_id' migrando para 'evento_agenda_id'.
    """
    if not getattr(dj_settings, "ENABLE_EVENT_MIRROR", False):
        return
    try:
        from agenda.models import Evento
    except Exception:
        return
    meta = agendamento.metadata if isinstance(agendamento.metadata, dict) else {}
    # Compat: se versão anterior gravou 'evento_id', mover para 'evento_agenda_id'
    if "evento_id" in meta and "evento_agenda_id" not in meta:
        meta["evento_agenda_id"] = meta.pop("evento_id")
        agendamento.metadata = meta
        try:
            agendamento.save(update_fields=["metadata"])
            try:  # pragma: no cover
                EVENTO_METADATA_MIGRACOES_TOTAL.inc()
            except Exception:
                pass
        except Exception:
            pass
    evento_id = meta.get("evento_agenda_id")
    titulo_base = f"Agendamento #{agendamento.id}"
    if agendamento.servico_id and getattr(agendamento.servico, "nome_servico", None):
        titulo_base += f" - {agendamento.servico.nome_servico}"  # type: ignore
    # Criar
    if not evento_id and criar_se_ausente:
        try:
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
            meta["evento_agenda_id"] = ev.id
            agendamento.metadata = meta
            agendamento.save(update_fields=["metadata"])
        except Exception:
            try:  # pragma: no cover
                MIRROR_FALHAS_TOTAL.inc()
            except Exception:
                pass
            return
    elif evento_id:
        try:
            ev = Evento.objects.filter(id=evento_id, tenant=agendamento.tenant).first()
            if not ev and criar_se_ausente:
                return _mirror_evento(agendamento, criar_se_ausente=True)
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
        except Exception:
            try:  # pragma: no cover
                MIRROR_FALHAS_TOTAL.inc()
            except Exception:
                pass
            return


class SlotService:
    @staticmethod
    def reservar(slot: Slot, quantidade: int = 1):
        """Reserva atomicamente capacidade de um slot e atualiza gauges/cache."""
        if quantidade < 1:
            raise ValueError("Quantidade inválida")
        with transaction.atomic():
            locked = Slot.objects.select_for_update().get(pk=slot.pk)
            if not locked.disponivel:
                raise ValueError("Slot indisponível")
            from django.conf import settings as _s

            limite = locked.capacidade_total
            if getattr(_s, "ENABLE_CONTROLLED_OVERBOOK", False):
                limite += getattr(_s, "AGENDAMENTOS_OVERBOOK_EXTRA", 1)
            if locked.capacidade_utilizada + quantidade > limite:
                raise ValueError("Slot indisponível")
            locked.capacidade_utilizada += quantidade
            locked.save(update_fields=["capacidade_utilizada"])
        slot.refresh_from_db(fields=["capacidade_utilizada"])
        bump_slots_cache_version()
        _update_capacity_gauges(slot.tenant_id)
        return slot

    @staticmethod
    def gerar_slots(disponibilidade: Disponibilidade):
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
        _update_capacity_gauges(disponibilidade.tenant_id)
        return created, existentes


class AgendamentoService:
    @staticmethod
    def criar(
        *,
        tenant,
        cliente,
        profissional,
        data_inicio,
        data_fim=None,
        origem,
        slot=None,
        tipo_servico=None,
        servico=None,
        metadata=None,
        user=None,
    ):
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
            try:  # pragma: no cover
                AGENDAMENTOS_CRIACAO_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise

    @staticmethod
    def _criar_impl(
        *,
        tenant,
        cliente,
        profissional,
        data_inicio,
        data_fim=None,
        origem,
        slot=None,
        tipo_servico=None,
        servico=None,
        metadata=None,
        user=None,
    ):
        from servicos.models import Servico as Serv

        proc_obj = None
        # Flag para exigir servico
        from django.conf import settings as dj_settings

        require_serv = getattr(dj_settings, "REQUIRE_SERVICO", False)
        if require_serv and not servico:
            raise ValueError("Serviço obrigatório (REQUIRE_SERVICO habilitado)")
        if servico:
            if isinstance(servico, (int, str)):
                try:
                    proc_obj = Serv.objects.get(id=servico, tenant=tenant, ativo=True, is_clinical=True)
                except Serv.DoesNotExist:
                    raise ValueError("Serviço inválido")
            else:
                proc_obj = servico
            # Perfil clínico associado (campos específicos)
            perfil_clinico = getattr(proc_obj, "perfil_clinico", None)
            # Validação de competência Profissional x Serviço (feature flag)
            if getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
                from .models import ProfissionalProcedimento

                ok = ProfissionalProcedimento.objects.filter(
                    tenant=tenant,
                    profissional=profissional,
                    servico=proc_obj,
                    ativo=True,
                ).exists()
                if not ok:
                    raise ValueError("Profissional não habilitado para este serviço")
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
                    raise ValueError("Intervalo mínimo entre sessões não atendido")
            # Duração automática se não fornecida
            if data_fim is None:
                dur_est = getattr(perfil_clinico, "duracao_estimada", None)
                if dur_est:
                    data_fim = data_inicio + dur_est
        # Conflito manual somente após definir data_fim
        if not slot:
            if not data_fim:
                raise ValueError("data_fim obrigatório")
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
                raise ValueError("Conflito de horário para o profissional (agendamento manual)")
        if not data_fim:
            raise ValueError("data_fim obrigatório")
        if data_fim <= data_inicio:
            raise ValueError("data_fim deve ser maior que data_inicio")
        if slot and proc_obj:
            # Heurística simples de incompatibilidade (slot único curto vs duração longa)
            if (data_fim - data_inicio).total_seconds() > 3600:  # >1h
                raise ValueError("Duração do serviço maior que o slot disponível")
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
            if ag.servico_id:
                diff["servico_id"] = ag.servico_id
            diff["data_inicio"] = ag.data_inicio.isoformat()
            diff["data_fim"] = ag.data_fim.isoformat()
            diff["profissional_id"] = ag.profissional_id
            AuditoriaAgendamento.objects.create(
                agendamento=ag, user=user, tipo_evento="CRIACAO", para_status=ag.status, diff=diff or None
            )
            nome_proc = getattr(proc_obj, "nome", None) or "Serviço"
            notificar_profissional_e_clientes(
                agendamento=ag,
                titulo_prof=f"Novo Agendamento - {nome_proc}",
                msg_prof=f"Agendamento #{ag.id} ({nome_proc}) criado para {ag.cliente} em {ag.data_inicio}.",
                titulo_cli=f"Seu Agendamento - {nome_proc}",
                msg_cli=f"Seu agendamento #{ag.id} ({nome_proc}) foi criado para {ag.data_inicio}.",
                tipo="info",
            )
            # Mirror de evento (fora do bloco crítico de criação de auditoria já executado)
            _mirror_evento(ag)
            return ag

    @staticmethod
    def cancelar(agendamento: Agendamento, *, motivo: str, user=None):
        try:
            if agendamento.status in ["CANCELADO", "CONCLUIDO"]:
                return agendamento
            if agendamento.origem == "CLIENTE":  # antecedência só para cliente
                from django.utils import timezone

                antecedencia = (agendamento.data_inicio - timezone.now()).total_seconds() / 60.0
                if antecedencia < settings.AGENDAMENTOS_CANCEL_ANTECEDENCIA_MINUTOS:
                    raise ValueError("Cancelamento não permitido dentro da antecedência mínima")
        except ValueError:
            try:  # pragma: no cover
                AGENDAMENTOS_CANCELAMENTO_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise
        anterior = agendamento.status
        agendamento.status = "CANCELADO"
        agendamento.save(update_fields=["status", "updated_at"])
        if agendamento.slot:
            from django.conf import settings as _s

            with transaction.atomic():
                locked = Slot.objects.select_for_update().get(pk=agendamento.slot_id)
                if locked.capacidade_utilizada > 0:
                    locked.capacidade_utilizada -= 1
                    locked.save(update_fields=["capacidade_utilizada"])
                    bump_slots_cache_version()
                    _update_capacity_gauges(locked.tenant_id)
                # Promoção automática da waitlist (primeiro ATIVO) se vaga liberada
                if getattr(_s, "ENABLE_WAITLIST", False):
                    limite = locked.capacidade_total
                    if getattr(_s, "ENABLE_CONTROLLED_OVERBOOK", False):
                        limite += getattr(_s, "AGENDAMENTOS_OVERBOOK_EXTRA", 1)
                    if locked.capacidade_utilizada < limite:  # há vaga
                        entry = (
                            locked.waitlist.select_for_update()
                            .filter(status="ATIVO")
                            .order_by("prioridade", "created_at")
                            .first()
                        )
                        if entry:
                            # Criar novo agendamento para cliente promovido
                            inicio = locked.horario
                            # Calcular fim (usa duração slot ou disponibilidade)
                            disp = locked.disponibilidade
                            from datetime import timedelta as _td

                            fim = inicio + _td(minutes=disp.duracao_slot_minutos)
                            novo_ag = Agendamento.objects.create(
                                tenant=locked.tenant,
                                cliente=entry.cliente,
                                profissional=locked.profissional,
                                slot=locked,
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
                                motivo=f"Promoção automática após cancelamento #{agendamento.id}",
                            )
                            try:  # pragma: no cover
                                WAITLIST_PROMOCOES_TOTAL.inc()
                            except Exception:
                                pass
                            bump_slots_cache_version()
                            _update_capacity_gauges(locked.tenant_id)
                            # Notificações básicas
                            notificar_profissional_e_clientes(
                                agendamento=novo_ag,
                                titulo_prof="Waitlist Promovida",
                                msg_prof=f"Cliente {entry.cliente} promovido do waitlist para slot {locked.horario}.",
                                titulo_cli="Sua vaga ficou disponível",
                                msg_cli=f"Seu agendamento foi criado a partir da lista de espera para {locked.horario}.",
                                tipo="info",
                            )
        AuditoriaAgendamento.objects.create(
            agendamento=agendamento,
            user=user,
            tipo_evento="CANCELAMENTO",
            de_status=anterior,
            para_status="CANCELADO",
            motivo=motivo,
        )
        nome_proc = getattr(agendamento.servico, "nome_servico", None) or "Serviço"
        notificar_profissional_e_clientes(
            agendamento=agendamento,
            titulo_prof=f"Agendamento Cancelado - {nome_proc}",
            msg_prof=f"Agendamento #{agendamento.id} ({nome_proc}) cancelado. Motivo: {motivo}",
            titulo_cli=f"Agendamento Cancelado - {nome_proc}",
            msg_cli=f"Seu agendamento #{agendamento.id} ({nome_proc}) foi cancelado. Motivo: {motivo}",
            tipo="warning",
        )
        _mirror_evento(agendamento, criar_se_ausente=False)
        return agendamento

    @staticmethod
    def reagendar(
        agendamento: Agendamento,
        *,
        novo_slot: Slot = None,
        nova_data_inicio=None,
        nova_data_fim=None,
        user=None,
        motivo=None,
    ):
        try:
            if agendamento.status == "CANCELADO":
                raise ValueError("Não reagendar agendamento cancelado")
            cadeia = 0
            ref = agendamento
            while ref.referencia_anterior_id and cadeia <= settings.AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX:
                cadeia += 1
                ref = ref.referencia_anterior
            if cadeia >= settings.AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX:
                raise ValueError("Limite de reagendamentos excedido")
        except ValueError:
            try:  # pragma: no cover
                AGENDAMENTOS_REAGENDAMENTO_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise
        AgendamentoService.cancelar(agendamento, motivo=motivo or "Reagendado", user=user)
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
                        from datetime import timedelta as _td

                        nova_data_fim = nova_data_inicio + _td(minutes=disp.duracao_slot_minutos)
        if not nova_data_inicio or not nova_data_fim:
            raise ValueError("Datas obrigatórias para novo agendamento")
        antes_proc = agendamento.servico_id
        antes_inicio = agendamento.data_inicio
        antes_fim = agendamento.data_fim
        antes_prof = agendamento.profissional_id
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
        diff = {}
        if antes_proc != novo.servico_id:
            diff["servico_de"] = antes_proc
            diff["servico_para"] = novo.servico_id
        if antes_inicio != novo.data_inicio:
            diff["data_inicio_de"] = antes_inicio.isoformat()
            diff["data_inicio_para"] = novo.data_inicio.isoformat()
        if antes_fim != novo.data_fim:
            diff["data_fim_de"] = antes_fim.isoformat()
            diff["data_fim_para"] = novo.data_fim.isoformat()
        if antes_prof != novo.profissional_id:
            diff["profissional_de"] = antes_prof
            diff["profissional_para"] = novo.profissional_id
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
            msg_prof=f"Agendamento #{novo.id} ({nome_proc}) reagendado (anterior #{agendamento.id}).",
            titulo_cli=f"Agendamento Reagendado - {nome_proc}",
            msg_cli=f"Seu agendamento ({nome_proc}) foi reagendado para {novo.data_inicio}. (original #{agendamento.id})",
            tipo="info",
        )
        _mirror_evento(novo)
        # Se mudou slot (novo_slot), capacidade já foi ajustada -> gauges/cache atualizados pelas operações anteriores
        return novo

    @staticmethod
    def checkin(agendamento: Agendamento, *, user=None):
        try:
            if agendamento.status != "CONFIRMADO":
                raise ValueError("Só é possível dar check-in em agendamentos CONFIRMADO")
            pendencias = (
                (agendamento.metadata or {}).get("pendencias") if isinstance(agendamento.metadata, dict) else None
            )
            if pendencias:
                raise ValueError("Pendências clínicas não resolvidas: " + ", ".join(pendencias))
        except ValueError:
            try:  # pragma: no cover
                AGENDAMENTOS_CHECKIN_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise
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
    def concluir(agendamento: Agendamento, *, user=None):
        try:
            if agendamento.status not in ["EM_ANDAMENTO", "CONFIRMADO"]:
                raise ValueError("Conclusão só permitida para EM_ANDAMENTO ou CONFIRMADO")
        except ValueError:
            try:  # pragma: no cover
                AGENDAMENTOS_CONCLUSAO_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise
        anterior = agendamento.status
        agendamento.status = "CONCLUIDO"
        agendamento.save(update_fields=["status", "updated_at"])
        AuditoriaAgendamento.objects.create(
            agendamento=agendamento, user=user, tipo_evento="CONCLUSAO", de_status=anterior, para_status="CONCLUIDO"
        )
        _mirror_evento(agendamento, criar_se_ausente=False)
        return agendamento

    @staticmethod
    def resolver_pendencias(agendamento: Agendamento, *, user=None):
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
    def inscrever_waitlist(slot: Slot, *, cliente, prioridade=100):
        from django.conf import settings

        if not getattr(settings, "ENABLE_WAITLIST", False):
            raise ValueError("Waitlist desabilitada")
        obj, created = WaitlistEntry.objects.get_or_create(
            tenant=slot.tenant, slot=slot, cliente=cliente, defaults={"prioridade": prioridade}
        )
        if not created:
            obj.prioridade = prioridade
            obj.save(update_fields=["prioridade"])
        return obj


class SchedulingService:
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
    def gerar_slots(disponibilidade: Disponibilidade):
        return SlotService.gerar_slots(disponibilidade)

    @staticmethod
    def reservar_slot(slot: Slot, quantidade: int = 1):
        try:
            slot = SlotService.reservar(slot, quantidade=quantidade)
            try:  # pragma: no cover
                SLOTS_RESERVADOS_TOTAL.inc()
            except Exception:
                pass
            return slot
        except Exception:
            try:  # pragma: no cover
                SLOTS_RESERVA_ERROS_TOTAL.inc()
            except Exception:
                pass
            raise

    # Agendamentos --------------------------------------------------------
    @staticmethod
    def criar_agendamento(**kwargs):
        from time import monotonic

        t0 = monotonic()
        ag = AgendamentoService.criar(**kwargs)
        dur = monotonic() - t0
        try:  # pragma: no cover
            AGENDAMENTOS_CRIADOS_TOTAL.inc()
            H_CRIA.observe(dur)
        except Exception:
            pass
        return ag

    @staticmethod
    def cancelar_agendamento(agendamento: Agendamento, *, motivo: str, user=None):
        from time import monotonic

        t0 = monotonic()
        status_antes = agendamento.status
        ag = AgendamentoService.cancelar(agendamento, motivo=motivo, user=user)
        dur = monotonic() - t0
        if status_antes != "CANCELADO" and ag.status == "CANCELADO":
            try:  # pragma: no cover
                AGENDAMENTOS_CANCELADOS_TOTAL.inc()
                H_CANCELA.observe(dur)
            except Exception:
                pass
        return ag

    @staticmethod
    def reagendar_agendamento(
        agendamento: Agendamento,
        *,
        novo_slot: Slot = None,
        nova_data_inicio=None,
        nova_data_fim=None,
        user=None,
        motivo=None,
    ):
        from time import monotonic

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
        try:  # pragma: no cover
            AGENDAMENTOS_REAGENDADOS_TOTAL.inc()
            H_REAGENDA.observe(dur)
        except Exception:
            pass
        return novo

    @staticmethod
    def checkin(agendamento: Agendamento, *, user=None):
        ag = AgendamentoService.checkin(agendamento, user=user)
        try:  # pragma: no cover
            AGENDAMENTOS_CHECKIN_TOTAL.inc()
        except Exception:
            pass
        return ag

    @staticmethod
    def concluir(agendamento: Agendamento, *, user=None):
        ag = AgendamentoService.concluir(agendamento, user=user)
        try:  # pragma: no cover
            AGENDAMENTOS_CONCLUIDOS_TOTAL.inc()
        except Exception:
            pass
        return ag

    @staticmethod
    def resolver_pendencias(agendamento: Agendamento, *, user=None):
        return AgendamentoService.resolver_pendencias(agendamento, user=user)

    @staticmethod
    def inscrever_waitlist(slot: Slot, *, cliente, prioridade=100):
        obj = AgendamentoService.inscrever_waitlist(slot, cliente=cliente, prioridade=prioridade)
        try:  # pragma: no cover
            WAITLIST_INSCRICOES_TOTAL.inc()
        except Exception:
            pass
        return obj

    @staticmethod
    def sync_evento(agendamento: Agendamento):
        """Força sincronização (criação/atualização) do evento espelho se flag habilitada.
        Retorna o id do evento (ou None se desabilitado/não criado)."""
        _mirror_evento(agendamento, criar_se_ausente=True)
        try:  # pragma: no cover
            EVENTO_SYNC_TOTAL.inc()
        except Exception:
            pass
        # Recarrega metadata atual (pode ter sido alterada por _mirror_evento)
        agendamento.refresh_from_db(fields=["metadata"])
        meta = agendamento.metadata if isinstance(agendamento.metadata, dict) else {}
        if "evento_id" in meta:
            # Se ainda não existe chave nova, copia o valor
            if "evento_agenda_id" not in meta:
                meta["evento_agenda_id"] = meta["evento_id"]
            # Remove sempre a chave legado para evitar duplicidade
            meta.pop("evento_id", None)
            try:
                agendamento.metadata = meta
                agendamento.save(update_fields=["metadata"])
            except Exception:
                pass
        return meta.get("evento_agenda_id")

    # Alias curtos (legado)
    criar = criar_agendamento
    cancelar = cancelar_agendamento
    reagendar = reagendar_agendamento

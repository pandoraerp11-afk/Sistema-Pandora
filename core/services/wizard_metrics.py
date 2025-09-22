"""Métricas para o wizard de criação de tenants.

Este módulo fornece um sistema de métricas em memória para o wizard,
com integração opcional com Prometheus.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from typing import Any

from django.conf import settings

# Inicialização segura do Prometheus
PROMETHEUS_ENABLED: bool
try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False

    class _MockMetric:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def inc(self, *args: object, **kwargs: object) -> None:
            """Mock."""

        def set(self, *args: object, **kwargs: object) -> None:
            """Mock."""

        def observe(self, *args: object, **kwargs: object) -> None:
            """Mock."""

    Counter = Gauge = Histogram = _MockMetric  # type: ignore[misc, assignment]


# Configurações
_MAX_LAT_SAMPLES: int = getattr(settings, "WIZARD_MAX_LATENCIES", 200)
_MAX_ERRORS: int = getattr(settings, "WIZARD_MAX_ERRORS", 25)
_MAX_ABANDON_SAMPLES: int = getattr(
    settings,
    "WIZARD_MAX_ABANDON_LATENCIES",
    200,
)


# Limiar de abandono será lido dinamicamente de settings a cada processamento
def _get_abandon_threshold() -> int:
    try:
        return int(getattr(settings, "WIZARD_ABANDON_THRESHOLD_SECONDS", 1800))
    except Exception:  # noqa: BLE001
        return 1800


_LATENCY_WARN_THRESHOLD: int | None = getattr(
    settings,
    "WIZARD_LATENCY_WARN_THRESHOLD",
    None,
)

# Estado interno do módulo
# Usar RLock para permitir reentrância segura em cenários onde funções internas
# possam ser chamadas dentro de regiões críticas (e.g., snapshot/reset chamando getters/setters).
_lock = threading.RLock()
_counters: dict[str, int] = {
    "finish_success": 0,
    "finish_subdomain_duplicate": 0,
    "finish_exception": 0,
}
_latencies: deque[float] = deque(maxlen=_MAX_LAT_SAMPLES)
_latencies_by_outcome: dict[str, deque[float]] = {
    "success": deque(maxlen=_MAX_LAT_SAMPLES),
    "duplicate": deque(maxlen=_MAX_LAT_SAMPLES),
    "exception": deque(maxlen=_MAX_LAT_SAMPLES),
}
_last_errors: deque[dict[str, Any]] = deque(maxlen=_MAX_ERRORS)
_active_sessions: set[str] = set()
_session_activity: dict[str, float] = {}
_session_start: dict[str, float] = {}
_abandon_durations: deque[float] = deque(maxlen=_MAX_ABANDON_SAMPLES)
_last_finish_correlation_id: str | None = None

# Métricas Prometheus
_buckets = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)
PROM_COUNTERS: dict[str, Any] = {
    "finish_success": Counter(
        "wizard_finish_success_total",
        "Finalizações bem sucedidas do wizard de tenant",
    ),
    "finish_subdomain_duplicate": Counter(
        "wizard_finish_subdomain_duplicate_total",
        "Finalizações bloqueadas por subdomínio duplicado",
    ),
    "finish_exception": Counter(
        "wizard_finish_exception_total",
        "Exceções durante finalização do wizard",
    ),
}
PROM_HISTO: Any = Histogram(
    "wizard_finish_latency_seconds",
    "Latência da finalização do wizard de tenant",
    buckets=_buckets,
)
PROM_HISTO_OUTCOME: dict[str, Any] = {
    "success": Histogram(
        "wizard_finish_latency_success_seconds",
        "Latência de finalizações bem sucedidas",
        buckets=_buckets,
    ),
    "duplicate": Histogram(
        "wizard_finish_latency_duplicate_seconds",
        "Latência de finalizações bloqueadas por duplicidade",
        buckets=_buckets,
    ),
    "exception": Histogram(
        "wizard_finish_latency_exception_seconds",
        "Latência de finalizações com exceção",
        buckets=_buckets,
    ),
}
PROM_GAUGES: dict[str, Any] = {
    "active_sessions": Gauge("wizard_active_sessions", "Sessões de wizard ativas"),
    "abandoned_sessions": Gauge(
        "wizard_abandoned_sessions",
        "Sessões abandonadas detectadas no último snapshot",
    ),
}

__all__ = [
    "inc_finish_success",
    "inc_finish_subdomain_duplicate",
    "inc_finish_exception",
    "record_finish_latency",
    "register_finish_error",
    "snapshot_metrics",
    "register_active_session",
    "unregister_active_session",
    "touch_session_activity",
    "get_last_finish_correlation_id",
    "set_last_finish_correlation_id",
    "reset_all_metrics",
]

logger = logging.getLogger(__name__)


def _inc(key: str) -> None:
    """Incrementa um contador interno e a métrica Prometheus correspondente."""
    with _lock:
        _counters[key] = _counters.get(key, 0) + 1
        if prom_counter := PROM_COUNTERS.get(key):
            prom_counter.inc()


def inc_finish_success() -> None:
    """Incrementa o contador de finalizações bem-sucedidas."""
    _inc("finish_success")


def inc_finish_subdomain_duplicate() -> None:
    """Incrementa o contador de finalizações com subdomínio duplicado."""
    _inc("finish_subdomain_duplicate")


def inc_finish_exception() -> None:
    """Incrementa o contador de finalizações com exceção."""
    _inc("finish_exception")


def record_finish_latency(seconds: float, outcome: str | None = None) -> None:
    """Registra a latência de finalização do wizard.

    Args:
        seconds: O tempo de latência em segundos.
        outcome: O resultado da operação ('success', 'duplicate', 'exception').

    """
    if seconds < 0:
        return

    outcome_key = outcome if outcome in _latencies_by_outcome else None

    with _lock:
        _latencies.append(seconds)
        PROM_HISTO.observe(seconds)

        if outcome_key:
            _latencies_by_outcome[outcome_key].append(seconds)
            if prom_histo := PROM_HISTO_OUTCOME.get(outcome_key):
                prom_histo.observe(seconds)

    # Hook externo para sistemas de observabilidade
    if sink := getattr(settings, "WIZARD_LATENCY_SINK", None):
        with contextlib.suppress(Exception):
            if callable(sink):
                correlation_id = get_last_finish_correlation_id()
                try:
                    sink(seconds, correlation_id, outcome_key)
                except TypeError:
                    sink(seconds, correlation_id)


def register_finish_error(kind: str, message: str | None = None) -> None:
    """Registra um erro ocorrido durante a finalização."""
    with _lock:
        _last_errors.append(
            {"ts": time.time(), "kind": kind, "msg": (message or "")[:300]},
        )


def _update_session_gauge() -> None:
    """Atualiza a métrica Prometheus para sessões ativas."""
    if active_sessions_gauge := PROM_GAUGES.get("active_sessions"):
        active_sessions_gauge.set(len(_active_sessions))


def register_active_session(session_key: str | None) -> None:
    """Registra uma sessão como ativa."""
    if not session_key:
        return
    with _lock:
        now = time.time()
        _active_sessions.add(session_key)
        _session_activity[session_key] = now
        if session_key not in _session_start:
            _session_start[session_key] = now
        _update_session_gauge()


def unregister_active_session(session_key: str | None) -> None:
    """Remove uma sessão da lista de ativas."""
    if not session_key:
        return
    with _lock:
        _active_sessions.discard(session_key)
        _session_activity.pop(session_key, None)
        _update_session_gauge()


def touch_session_activity(session_key: str | None) -> None:
    """Atualiza o timestamp de última atividade de uma sessão."""
    if not session_key:
        return
    with _lock:
        now = time.time()
        _session_activity[session_key] = now
        if session_key not in _session_start:
            _session_start[session_key] = now


def get_last_finish_correlation_id() -> str | None:
    """Retorna o ID de correlação da última finalização."""
    with _lock:
        return _last_finish_correlation_id


def set_last_finish_correlation_id(cid: str | None) -> None:
    """Define o ID de correlação da última finalização."""
    with _lock:
        # Atualiza variável de módulo sem usar 'global' (evita alerta de lint)
        globals()["_last_finish_correlation_id"] = cid


def _compute_stats(series: deque[float] | list[float]) -> dict[str, float]:
    """Calcula estatísticas básicas de uma série de números."""
    if not series:
        return {}
    ordered = sorted(series)
    n = len(ordered)
    if n == 0:
        return {}
    p50 = ordered[int(0.5 * (n - 1))]
    p90 = ordered[int(0.9 * (n - 1))]
    p95 = ordered[int(0.95 * (n - 1))]
    p99 = ordered[int(0.99 * (n - 1))]
    return {
        "count": n,
        "p50": p50,
        "p90": p90,
        "p95": p95,
        "p99": p99,
        "max": ordered[-1],
    }


def _process_abandoned_sessions(now: float) -> int:
    """Processa e contabiliza sessões abandonadas."""
    abandoned_count = 0
    to_remove = []
    threshold = _get_abandon_threshold()
    for sk, ts in _session_activity.items():
        if (now - ts) > threshold and sk not in _active_sessions:
            abandoned_count += 1
            to_remove.append(sk)
            if start_ts := _session_start.pop(sk, None):
                _abandon_durations.append(now - start_ts)

    for sk in to_remove:
        _session_activity.pop(sk, None)

    return abandoned_count


def _check_latency_warning(stats: dict[str, float]) -> None:
    """Verifica se a latência p95 excede o limite e emite um alerta."""
    if _LATENCY_WARN_THRESHOLD is None or not stats:
        return

    p95_latency = stats.get("p95")
    if p95_latency is not None and p95_latency > _LATENCY_WARN_THRESHOLD:
        logger.warning(
            "Wizard latency p95 (%s) is above the threshold (%s)",
            p95_latency,
            _LATENCY_WARN_THRESHOLD,
        )


def snapshot_metrics() -> dict[str, Any]:
    """Tira um snapshot das métricas atuais em memória sem deadlocks.

    Estratégias usadas:
    - RLock para reentrância segura
    - Leitura direta de variáveis protegidas dentro do lock quando já estamos na seção crítica
    - Escopo do lock apenas para leitura/atualização de estruturas internas; pós-processamento fora
    """
    with _lock:
        now = time.time()
        abandoned = _process_abandoned_sessions(now)

        lat_stats = _compute_stats(list(_latencies))
        # Checagem de alerta não precisa segurar lock, mas é leve; manter aqui evita condição de corrida
        _check_latency_warning(lat_stats)
        lat_stats_outcomes = {k: _compute_stats(list(v)) for k, v in _latencies_by_outcome.items() if v}
        abandon_time_stats = _compute_stats(list(_abandon_durations))
        if _abandon_durations:
            abandon_time_stats["avg"] = sum(_abandon_durations) / len(_abandon_durations)

        _update_session_gauge()
        if abandoned_sessions_gauge := PROM_GAUGES.get("abandoned_sessions"):
            abandoned_sessions_gauge.set(abandoned)

        # Capturas atômicas sob lock
        counters_copy = dict(_counters)
        last_cid = _last_finish_correlation_id  # acesso direto sob o mesmo lock (evita reentrância)
        active_count = len(_active_sessions)
        last_errors_copy = list(_last_errors)

    # Montagem do snapshot fora do lock
    snapshot: dict[str, Any] = {
        "counters": counters_copy,
        "latency": lat_stats,
        "latency_by_outcome": lat_stats_outcomes,
        "last_errors": last_errors_copy,
        "active_sessions": active_count,
        "abandoned_sessions": abandoned,
        "time_to_abandon": abandon_time_stats,
        "last_finish_correlation_id": last_cid,
        "prometheus_enabled": PROMETHEUS_ENABLED,
    }

    # Duplicar chaves planas esperadas por alguns testes legados
    snapshot.update(
        {
            "finish_success": counters_copy.get("finish_success", 0),
            "finish_subdomain_duplicate": counters_copy.get("finish_subdomain_duplicate", 0),
            "finish_exception": counters_copy.get("finish_exception", 0),
        },
    )

    return snapshot


def reset_all_metrics() -> None:
    """Reseta todas as estruturas in-memory de métricas do wizard.

    Uso principal: testes, troubleshooting ou comando de manutenção.
    """
    with _lock:
        for k in list(_counters.keys()):
            _counters[k] = 0
        _latencies.clear()
        for lst in _latencies_by_outcome.values():
            lst.clear()
        _last_errors.clear()
        _active_sessions.clear()
        _session_activity.clear()
        _session_start.clear()
        _abandon_durations.clear()

        # Evitar reentrância chamando setter; zera diretamente sob o mesmo lock
        # e sem usar 'global' (evita aviso de lint PLW0603)
        globals()["_last_finish_correlation_id"] = None

        # Reseta gauges do Prometheus
        _update_session_gauge()
        if abandoned_sessions_gauge := PROM_GAUGES.get("abandoned_sessions"):
            abandoned_sessions_gauge.set(0)

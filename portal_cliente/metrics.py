"""Métricas Prometheus específicas do Portal Cliente.

Fornece counters/histogram com fallback (_Noop) quando `prometheus_client`
não está instalado. Usa `Any` para evitar conflitos de tipagem entre os tipos
reais e o fallback durante análise estática (mypy/pylance).
"""

from __future__ import annotations

# ruff: noqa: I001  # Import sorting sinalizando falso-positivo; bloco revisado manualmente
import time
from contextlib import contextmanager
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - apenas para tipagem
    from collections.abc import Generator

# Declaração antecipada com Any para permitir atribuição posterior a Counter/Histogram ou _Noop.
PORTAL_CLIENTE_PAGE_HITS: Any
PORTAL_CLIENTE_LOGIN: Any
PORTAL_CLIENTE_ACTION_DURATION: Any
PORTAL_CLIENTE_THROTTLE_HITS: Any
PORTAL_CLIENTE_ACTION_TOTAL: Any
PORTAL_CLIENTE_ACTION_ERROR_KIND_TOTAL: Any


class _Noop:  # pragma: no cover - comportamento trivial
    def labels(self, *_: object, **__: object) -> _Noop:
        return self

    def inc(self, *_: object, **__: object) -> None:
        return None

    def observe(self, *_: object, **__: object) -> None:
        return None


try:  # pragma: no cover - só executado se prometheus_client existir
    from prometheus_client import Counter, Histogram

    PORTAL_CLIENTE_PAGE_HITS = Counter(
        "portal_cliente_page_hits_total",
        "Hits de páginas portal cliente",
        ["page"],
    )
    PORTAL_CLIENTE_LOGIN = Counter(
        "portal_cliente_login_total",
        "Logins portal cliente",
    )
    PORTAL_CLIENTE_ACTION_DURATION = Histogram(
        "portal_cliente_action_seconds",
        "Duração ações portal cliente",
        ["action"],
    )
    PORTAL_CLIENTE_THROTTLE_HITS = Counter(
        "portal_cliente_throttle_total",
        "Ocorrências de throttling em endpoints portal cliente",
        ["endpoint"],
    )
    PORTAL_CLIENTE_ACTION_TOTAL = Counter(
        "portal_cliente_action_total",
        "Total de ações do portal cliente categorizadas por status",
        ["action", "status"],
    )
    PORTAL_CLIENTE_ACTION_ERROR_KIND_TOTAL = Counter(
        "portal_cliente_action_error_kind_total",
        "Total de erros classificados por tipo lógico (kind) em ações portal cliente",
        ["action", "kind"],
    )
except (ImportError, RuntimeError):  # pragma: no cover
    PORTAL_CLIENTE_PAGE_HITS = _Noop()
    PORTAL_CLIENTE_LOGIN = _Noop()
    PORTAL_CLIENTE_ACTION_DURATION = _Noop()
    PORTAL_CLIENTE_THROTTLE_HITS = _Noop()
    PORTAL_CLIENTE_ACTION_TOTAL = _Noop()
    PORTAL_CLIENTE_ACTION_ERROR_KIND_TOTAL = _Noop()


def inc_throttle(endpoint: str) -> None:
    """Incrementa contador de throttling (silencioso quando noop)."""
    PORTAL_CLIENTE_THROTTLE_HITS.labels(endpoint=endpoint).inc()


def inc_action(action: str, status: str) -> None:
    """Incrementa contador de ação com status (success|error)."""
    PORTAL_CLIENTE_ACTION_TOTAL.labels(action=action, status=status).inc()


def inc_action_error_kind(action: str, kind: str) -> None:
    """Incrementa contador granular de erro (kind normalizado)."""
    safe_kind = kind.replace(" ", "_").replace("-", "_").lower()
    PORTAL_CLIENTE_ACTION_ERROR_KIND_TOTAL.labels(action=action, kind=safe_kind).inc()


@contextmanager
def track_action(action: str) -> Generator[None, None, None]:
    """Context manager que observa duração de uma ação do portal."""
    start = time.time()
    try:
        yield
    finally:
        PORTAL_CLIENTE_ACTION_DURATION.labels(action=action).observe(time.time() - start)

"""Helpers reutilizáveis de throttling para endpoints do portal cliente."""

from __future__ import annotations

from collections.abc import Callable

from django.core.cache import cache
from django.utils import timezone

from .conf import (
    get_listas_throttle_limit,
    get_slots_throttle_limit,
    get_throttle_avaliar_limit,
    get_throttle_checkin_limit,
    get_throttle_finalizar_limit,
)

# Mapa padrão de limites (requisições por janela). Janela default 60s.
LimitValue = int | Callable[[], int]
_ENDPOINT_LIMITS: dict[str, tuple[LimitValue, int]] = {
    "slots": (get_slots_throttle_limit, 60),
    "servicos": (get_listas_throttle_limit, 60),
    "profissionais": (get_listas_throttle_limit, 60),
    # Endpoints de ação Fase 2
    "status": (20, 60),
    # Check-in / finalizar / avaliar agora parametrizados via conf getters
    "checkin": (get_throttle_checkin_limit, 60),
    "finalizar": (get_throttle_finalizar_limit, 60),
    "avaliar": (get_throttle_avaliar_limit, 60),
}


def get_endpoint_limit(key_base: str) -> tuple[int, int]:
    """Retorna (limit, window_seconds) para um endpoint.

    Para listas (slots/servicos/profissionais) os limites são dinâmicos via conf.
    Para endpoints de ação são valores fixos simples.
    """
    val = _ENDPOINT_LIMITS.get(key_base)
    if not val:
        # Fallback seguro
        return (30, 60)
    limit, window = val
    # Se limit for callable (config dinâmica), resolve agora
    if callable(limit):
        return (int(limit()), window)
    return (int(limit), window)


def _build_keys(user_id: int, key_base: str, scope: str | int | None) -> tuple[str, str]:
    base = f"portal_throttle:{key_base}:{user_id}"
    if scope is not None:
        base = f"{base}:{scope}"
    return base, f"{base}:start"


def check_throttle(
    user_id: int,
    key_base: str,
    limit: int,
    window_seconds: int,
    scope: str | int | None = None,
) -> bool:
    """Incrementa contador e retorna True se excedido.

    Também persiste timestamp inicial da janela para cálculo de Retry-After
    dinâmico por quem consome (views). Chaves usadas:
      - {base} -> contador
      - {base}:start -> epoch inicial
    """
    cache_key, start_key = _build_keys(user_id, key_base, scope)
    current = cache.get(cache_key, 0)
    if current >= limit:
        return True
    if current == 0:
        cache.set(cache_key, 1, window_seconds)
        # Timestamp inicial salvo com mesmo TTL
        cache.set(start_key, int(timezone.now().timestamp()), window_seconds)
    else:
        cache.incr(cache_key)
    return False


def check_throttle_auto(user_id: int, key_base: str, scope: str | int | None = None) -> bool:
    """Return True se limite excedido (com escopo opcional)."""
    limit, window = get_endpoint_limit(key_base)
    return check_throttle(user_id, key_base, limit, window, scope=scope)


def get_retry_after_seconds(user_id: int, key_base: str, scope: str | int | None = None) -> int:
    """Calcula segundos restantes da janela de throttling.

    Se não encontrar timestamp inicial, retorna fallback 60.
    """
    limit, window = get_endpoint_limit(key_base)
    cache_key, start_key = _build_keys(user_id, key_base, scope)
    # se contador nem começou, janela não ativa
    if cache.get(cache_key) is None:
        return window
    started_at = cache.get(start_key)
    if not started_at:
        return window
    elapsed = int(timezone.now().timestamp()) - int(started_at)
    remaining = window - elapsed
    if remaining < 1:
        return 1
    return remaining

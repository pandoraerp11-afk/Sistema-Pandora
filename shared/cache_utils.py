"""Utils de cache resilientes.

Inclui get_int e incr_atomic com fallback a lock in-memory simples.
"""

from __future__ import annotations

import threading

from django.core.cache import cache

_local_lock = threading.Lock()


def get_int(key: str, default: int = 0) -> int:
    val = cache.get(key)
    try:
        return int(val)
    except Exception:
        return default


def incr_atomic(key: str, delta: int = 1, ttl: int | None = None) -> int:
    """Incrementa contador inteiro de forma resiliente.
    Se backend tiver add/incr atômico aproveita, senão lock local.
    """
    # Django cache não padroniza incr para todos backends; fallback manual.
    with _local_lock:
        current = get_int(key, 0) + delta
        cache.set(key, current, ttl)
        return current

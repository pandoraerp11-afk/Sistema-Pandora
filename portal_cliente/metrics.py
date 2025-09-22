"""Métricas Prometheus específicas do Portal Cliente."""

try:
    from prometheus_client import Counter, Histogram

    PORTAL_CLIENTE_PAGE_HITS = Counter("portal_cliente_page_hits_total", "Hits de páginas portal cliente", ["page"])
    PORTAL_CLIENTE_LOGIN = Counter("portal_cliente_login_total", "Logins portal cliente")
    PORTAL_CLIENTE_ACTION_DURATION = Histogram(
        "portal_cliente_action_seconds", "Duração ações portal cliente", ["action"]
    )
except Exception:  # pragma: no cover
    # Fallbacks vazios se prometheus_client indisponível
    class _Noop:
        def labels(self, *a, **k):
            return self

        def inc(self, *a, **k):
            return None

        def observe(self, *a, **k):
            return None

    PORTAL_CLIENTE_PAGE_HITS = PORTAL_CLIENTE_LOGIN = PORTAL_CLIENTE_ACTION_DURATION = _Noop()

import time
from contextlib import contextmanager


@contextmanager
def track_action(action):
    start = time.time()
    try:
        yield
    finally:
        PORTAL_CLIENTE_ACTION_DURATION.labels(action=action).observe(time.time() - start)

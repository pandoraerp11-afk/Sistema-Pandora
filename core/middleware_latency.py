"""Middleware simples para medir latência de requests e expor em métricas Prometheus."""

import time

from django.utils.deprecation import MiddlewareMixin

try:
    from prometheus_client import Histogram

    REQUEST_LATENCY = Histogram("pandora_request_latency_seconds", "Latência de requisições", ["path"])
except Exception:  # pragma: no cover

    class _Noop:
        def labels(self, *a, **k):
            return self

        def observe(self, *a, **k):
            return None

    REQUEST_LATENCY = _Noop()

EXCLUDE_PREFIXES = ["/static", "/media"]


class RequestLatencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        start = getattr(request, "_start_time", None)
        if start and not any(request.path.startswith(p) for p in EXCLUDE_PREFIXES):
            path_label = request.path.split("?")[0][:60]
            REQUEST_LATENCY.labels(path=path_label).observe(time.time() - start)
        return response

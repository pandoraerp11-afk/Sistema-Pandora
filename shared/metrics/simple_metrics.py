"""Camada de métricas simplificada.

Se prometheus_client estiver disponível, usa Counters/Histograms reais.
Caso contrário, fornece objetos no-op com mesma interface mínima (inc, observe).
"""

from __future__ import annotations

try:  # pragma: no cover - dependente de ambiente
    from prometheus_client import Counter as _PCCounter  # type: ignore
    from prometheus_client import Histogram as _PCHistogram
except Exception:  # pragma: no cover
    _PCCounter = _PCHistogram = None  # type: ignore


class _NoOp:
    def labels(self, *_, **__):  # retorna self para encadeamento
        return self

    def inc(self, *_a, **_kw):
        return None

    def observe(self, *_a, **_kw):
        return None


def Counter(name: str, documentation: str, labelnames=None):  # type: ignore
    if _PCCounter is None:
        return _NoOp()
    try:
        if labelnames:
            return _PCCounter(name, documentation, labelnames)
        return _PCCounter(name, documentation)
    except Exception:  # pragma: no cover
        return _NoOp()


def Histogram(name: str, documentation: str, buckets=None):  # type: ignore
    if _PCHistogram is None:
        return _NoOp()
    try:
        if buckets:
            return _PCHistogram(name, documentation, buckets=buckets)
        return _PCHistogram(name, documentation)
    except Exception:  # pragma: no cover
        return _NoOp()

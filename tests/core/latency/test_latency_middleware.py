"""Testes do `RequestLatencyMiddleware`.

Valida:
* Registro de métricas (labels + observe) em rota normal.
* Ignora caminhos estáticos (/static/...).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.http import HttpRequest, HttpResponse

from core.middleware_latency import RequestLatencyMiddleware

pytestmark = [pytest.mark.django_db]


class DummyRequest(HttpRequest):
    """Request mínimo com atributo path customizado.

    Apenas define atributo `path` tipado como str para o middleware; não possui
    comportamento adicional. Docstring adicionada para satisfazer D107.
    """

    def __init__(self, path: str = "/x") -> None:  # noqa: D107 - docstring na classe já explica
        super().__init__()
        self.path = path  # str


def test_latency_middleware_observes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica registro de métricas em rota não estática."""
    observed: dict[str, Any] = {}

    class _Recorder:
        def labels(self, path: str) -> _Recorder:  # pragma: no cover - simples atribuição
            observed["path"] = path
            return self

        def observe(self, value: float) -> None:  # pragma: no cover
            observed["value"] = value

    monkeypatch.setattr("core.middleware_latency.REQUEST_LATENCY", _Recorder())

    called: dict[str, Any] = {}

    def get_response(_req: HttpRequest) -> HttpResponse:
        """Simula view devolvendo 200 e aceita HttpRequest padrão."""
        called["ok"] = True
        return HttpResponse("OK")

    mw = RequestLatencyMiddleware(get_response)
    req = DummyRequest("/api/test-endpoint")
    resp = mw(req)
    assert resp is not None
    assert called.get("ok") is True
    assert observed["path"].startswith("/api/test-endpoint")
    assert observed["value"] >= 0


def test_latency_middleware_excludes_static(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que caminhos estáticos não disparam coleta de métricas."""
    # Lista de eventos potencialmente heterogênea (path:str ou valor:float) —
    # tipada como list[object] para evitar conflito mypy caso algo seja adicionado.
    calls: list[object] = []

    class _Recorder:
        def labels(self, path: str) -> _Recorder:  # pragma: no cover - registro trivial
            calls.append(path)
            return self

        def observe(self, value: float) -> None:  # pragma: no cover
            calls.append(value)

    monkeypatch.setattr("core.middleware_latency.REQUEST_LATENCY", _Recorder())

    def _ok(_req: HttpRequest) -> HttpResponse:
        """View dummy para caminho estático."""
        return HttpResponse("OK")

    mw = RequestLatencyMiddleware(_ok)
    req = DummyRequest("/static/css/app.css")
    mw(req)
    assert calls == []

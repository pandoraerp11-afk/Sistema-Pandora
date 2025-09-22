import pytest

from core.middleware_latency import RequestLatencyMiddleware

pytestmark = [pytest.mark.django_db]


class DummyRequest:
    def __init__(self, path="/x"):
        self.path = path


def test_latency_middleware_observes(monkeypatch):
    observed = {}

    class _Recorder:
        def labels(self, path):
            observed["path"] = path
            return self

        def observe(self, value):
            observed["value"] = value

    monkeypatch.setattr("core.middleware_latency.REQUEST_LATENCY", _Recorder())

    called = {}

    def get_response(req):
        called["ok"] = True
        return object()

    mw = RequestLatencyMiddleware(get_response)
    req = DummyRequest("/api/test-endpoint")
    resp = mw(req)  # usa fluxo padrão do MiddlewareMixin
    assert resp is not None
    assert called.get("ok") is True
    assert observed["path"].startswith("/api/test-endpoint")
    assert observed["value"] >= 0


def test_latency_middleware_excludes_static(monkeypatch):
    calls = []

    class _Recorder:
        def labels(self, path):
            calls.append(path)
            return self

        def observe(self, value):
            calls.append(value)

    monkeypatch.setattr("core.middleware_latency.REQUEST_LATENCY", _Recorder())
    mw = RequestLatencyMiddleware(lambda r: object())
    req = DummyRequest("/static/css/app.css")
    mw(req)
    assert calls == []  # não registrou

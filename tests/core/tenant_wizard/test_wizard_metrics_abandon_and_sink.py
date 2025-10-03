import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_wizard_metrics_abandoned_sessions(monkeypatch, client, settings):
    """Simula sessões inativas para validar cálculo de abandoned_sessions.
    Estratégia: força threshold baixo e injeta estado interno via imports diretos.
    """
    settings.WIZARD_ABANDON_THRESHOLD_SECONDS = 0.1
    staff = User.objects.create_user(username="staff3", email="s3@example.com", password="x12345678", is_staff=True)
    client.force_login(staff)

    # Simular duas sessões tocadas no passado e não ativas
    import time as _t

    from core.services import wizard_metrics as wm

    with wm._lock:  # acessar diretamente estruturas internas (teste de infra)
        wm._session_activity["sess_old_1"] = _t.time() - 999
        wm._session_activity["sess_old_2"] = _t.time() - 500
    url = reverse("core:wizard_metrics")
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()["wizard_metrics"]
    # Como threshold = 0.1, ambas devem ser consideradas abandonadas e removidas
    assert data["abandoned_sessions"] >= 2
    # Chamada subsequente não deve contar novamente (já prunadas)
    resp2 = client.get(url)
    data2 = resp2.json()["wizard_metrics"]
    assert data2["abandoned_sessions"] == 0


@pytest.mark.django_db
def test_wizard_metrics_latency_sink_and_correlation(monkeypatch, client, settings):
    """Valida que o hook externo recebe (latency, correlation_id, outcome) retrocompatível e que snapshot expõe last_finish_correlation_id."""
    calls = []

    # Implementa callable aceitando 3 args, simulando versão nova
    def _sink(lat, cid, outcome=None):
        calls.append((lat, cid, outcome))

    settings.WIZARD_LATENCY_SINK = _sink

    staff = User.objects.create_user(username="staff4", email="s4@example.com", password="x12345678", is_staff=True)
    client.force_login(staff)

    # Forçar registro manual simulando finalização
    from core.services import wizard_metrics as wm

    wm.set_last_finish_correlation_id("abc123cid999")
    wm.record_finish_latency(0.05)

    assert calls, "Hook de latency não foi chamado"
    lat, cid, outcome = calls[-1]
    assert cid == "abc123cid999"
    assert lat == 0.05
    assert outcome is None  # chamada manual sem outcome

    url = reverse("core:wizard_metrics")
    resp = client.get(url)
    assert resp.status_code == 200
    snapshot = resp.json()["wizard_metrics"]
    assert snapshot["last_finish_correlation_id"] == "abc123cid999"


@pytest.mark.django_db
def test_wizard_metrics_latency_outcomes_and_time_to_abandon(monkeypatch, client, settings):
    """Simula diferentes outcomes registrando latências e abandono com mock de tempo."""
    from core.services import wizard_metrics as wm

    # Mock time
    base = [1000.0]

    def fake_time():
        return base[0]

    monkeypatch.setattr(wm, "time", type("T", (), {"time": staticmethod(fake_time)}))
    settings.WIZARD_ABANDON_THRESHOLD_SECONDS = 10

    # Registrar sessões e atividades
    wm.register_active_session("s1")  # success futura
    wm.register_active_session("s2")  # duplicate futura
    wm.register_active_session("s3")  # exception futura

    # Avança tempo e registra latências com outcomes
    base[0] += 1
    wm.record_finish_latency(0.10, outcome="success")
    wm.unregister_active_session("s1")
    base[0] += 1
    wm.record_finish_latency(0.20, outcome="duplicate")
    wm.unregister_active_session("s2")
    base[0] += 1
    wm.record_finish_latency(0.30, outcome="exception")
    wm.unregister_active_session("s3")

    # Criar sessão que será abandonada
    wm.touch_session_activity("s4")  # start agora
    base[0] += 50  # ultrapassa threshold -> abandono

    snap = wm.snapshot_metrics()
    lat_by_outcome = snap["latency_by_outcome"]
    assert "success" in lat_by_outcome and lat_by_outcome["success"]["count"] >= 1
    assert "duplicate" in lat_by_outcome and lat_by_outcome["duplicate"]["count"] >= 1
    assert "exception" in lat_by_outcome and lat_by_outcome["exception"]["count"] >= 1
    assert snap["abandoned_sessions"] >= 1
    # time_to_abandon deve ter estatísticas básicas
    tta = snap["time_to_abandon"]
    assert "count" in tta and tta["count"] >= 1
    assert "p50" in tta

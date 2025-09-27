import pytest
from django.core.management import call_command

from core.services import wizard_metrics


@pytest.mark.django_db
def test_wizard_metrics_reset_command(monkeypatch):
    # Simular alguns registros
    for i in range(3):
        wizard_metrics.register_active_session(f"sess{i}")
    # Incrementar counters explicitamente
    wizard_metrics.inc_finish_success()
    wizard_metrics.inc_finish_subdomain_duplicate()
    wizard_metrics.record_finish_latency(1.25, outcome="success")
    wizard_metrics.record_finish_latency(2.50, outcome="duplicate")

    before = wizard_metrics.snapshot_metrics()
    # counters expostos na chave 'counters'
    assert before["counters"]["finish_success"] == 1
    assert before["counters"]["finish_subdomain_duplicate"] == 1
    assert before["latency"]["count"] >= 2

    # Executa comando
    call_command("wizard_metrics_reset")

    after = wizard_metrics.snapshot_metrics()
    assert after["counters"]["finish_success"] == 0
    assert after["counters"]["finish_subdomain_duplicate"] == 0
    assert after["counters"]["finish_exception"] == 0
    assert after["active_sessions"] == 0
    # Latências: ou vazio (sem chaves) ou 'count' inexistente
    assert after["latency"].get("count", 0) == 0

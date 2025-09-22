import pytest
from django.core.cache import cache
from django.core.management import call_command


@pytest.mark.django_db
def test_metrics_dump_list_and_reset(capsys):
    # Preparar algumas métricas artificiais
    cache.set("module_deny_count:TESTMOD:REASON_X", 5, 60)
    cache.set("perm_resolver:dummy", 1, 60)

    call_command("metrics_dump")
    out = capsys.readouterr().out
    assert "module_deny_count:TESTMOD:REASON_X=" in out
    assert "perm_resolver" in out

    call_command("metrics_dump", "--reset")
    out2 = capsys.readouterr().out
    assert "Reset concluído" in out2
    # Deve ter sido removido
    assert cache.get("module_deny_count:TESTMOD:REASON_X") is None

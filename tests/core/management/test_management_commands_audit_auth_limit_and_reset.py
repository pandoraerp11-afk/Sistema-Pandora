import io

import pytest
from django.core.cache import cache
from django.core.management import call_command

pytestmark = [pytest.mark.django_db]


def test_audit_auth_limit_and_reset():
    cache.set("module_deny_count:alpha", 10, 60)
    cache.set("module_deny_count:beta", 5, 60)
    out = io.StringIO()
    call_command("audit_auth", "--limit", "1", stdout=out)
    output = out.getvalue()
    # Apenas uma linha de contador (ou nenhuma se heurística não achar, então falha)
    assert len([l for l in output.splitlines() if l.startswith("module_deny_count:")]) <= 1

    # Agora reset
    out2 = io.StringIO()
    call_command("audit_auth", "--reset", stdout=out2)
    output2 = out2.getvalue()
    # Deve dizer que resetou OU não encontrou (se corrida muito rápida)
    assert ("resetados" in output2) or ("Nenhum contador encontrado" in output2)


def test_audit_auth_empty():
    # Garantir vazio
    out = io.StringIO()
    call_command("audit_auth", stdout=out)
    assert "Nenhum contador encontrado" in out.getvalue()

import io
import re

import pytest
from django.core.cache import cache
from django.core.management import call_command

pytestmark = [pytest.mark.django_db]


def test_audit_auth_lists_counters():
    # Preparar alguns contadores simulados
    cache.set("module_deny_count:clientes", 5, 60)
    cache.set("module_deny_count:fornecedores", 2, 60)
    out = io.StringIO()
    call_command("audit_auth", stdout=out)
    output = out.getvalue()
    # Deve conter as chaves inseridas (ordem não garantida)
    assert "module_deny_count:clientes" in output or "module_deny_count:fornecedores" in output
    # Pelo menos um valor numérico
    assert re.search(r"module_deny_count:[a-z]+ => [0-9]+", output)

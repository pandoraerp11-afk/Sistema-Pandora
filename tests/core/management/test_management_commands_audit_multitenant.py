import io

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.django_db]


def test_audit_multitenant_runs():
    out = io.StringIO()
    # Apenas verifica que comando executa sem exceção e imprime cabeçalho
    call_command("audit_multitenant", stdout=out)
    txt = out.getvalue()
    assert "Auditoria Multi-Tenant" in txt or "Iniciando Auditoria" in txt

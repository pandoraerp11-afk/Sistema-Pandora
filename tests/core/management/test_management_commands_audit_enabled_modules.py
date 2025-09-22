import io
import json

import pytest
from django.core.management import call_command

from core.models import Tenant

pytestmark = [pytest.mark.django_db]


def test_audit_enabled_modules_json_and_apply(monkeypatch):
    t = Tenant.objects.create(nome="Empresa X", slug="emp-x", enabled_modules={"legacy": ["a", "b"]})
    out = io.StringIO()
    call_command("audit_enabled_modules", "--json", stdout=out)
    data = json.loads(out.getvalue())
    assert data["total"] >= 1
    # Força normalização aplicando
    out2 = io.StringIO()
    call_command("audit_enabled_modules", "--apply", stdout=out2)
    t.refresh_from_db()
    assert isinstance(t.enabled_modules, dict)
    assert "modules" in t.enabled_modules

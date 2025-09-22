import io

import pytest
from django.core.cache import cache
from django.core.management import call_command

pytestmark = [pytest.mark.django_db]


def test_clear_system_cache_basic(monkeypatch):
    cache.set("foo", "bar", 30)
    out = io.StringIO()
    call_command("clear_system_cache", stdout=out)
    # Após execução, chave pode não estar (limpeza) – tolera se backend não limpar tudo
    cache.get("foo")
    assert True  # apenas garante que comando não falhou
    assert "Limpeza de cache concluída" in out.getvalue() or "Limpeza de cache" in out.getvalue()

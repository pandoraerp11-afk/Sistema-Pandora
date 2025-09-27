import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_command_finalizar_setup_smoke(monkeypatch):
    """Smoke test: roda command com flags para evitar operações caras e valida execução."""
    # Monkeypatch para evitar qualquer latência extra em migrations se já rodadas
    call_command("finalizar_setup_estoque", "--skip-migrate", "--no-permissoes", "--no-seed")

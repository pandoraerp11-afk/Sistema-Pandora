import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from user_management.models import PerfilUsuarioEstendido
from user_management.twofa import setup_2fa

pytestmark = [pytest.mark.django_db, pytest.mark.twofa]


def _bootstrap_perfis(qtd=2):
    User = get_user_model()
    perfis = []
    for i in range(qtd):
        u = User.objects.create_user(f"u2fa_cmd_{i}", password="x")
        # Perfil já é criado via sinal post_save; obter de forma idempotente
        try:
            perfil = u.perfil_estendido  # type: ignore[attr-defined]
        except AttributeError:
            perfil, _ = PerfilUsuarioEstendido.objects.get_or_create(user=u)
        setup_2fa(perfil)
        perfis.append(perfil)
    return perfis


def test_twofa_metrics_snapshot_and_reset(capsys):
    _bootstrap_perfis(1)
    call_command("twofa_metrics_snapshot")
    out1 = capsys.readouterr().out
    assert "SNAPSHOT_2FA" in out1
    call_command("twofa_metrics_snapshot", "--reset")
    out2 = capsys.readouterr().out
    assert "Counters reset" in out2


def test_twofa_status_report_json_and_detailed(capsys):
    _bootstrap_perfis(1)
    call_command("twofa_status_report", "--json", "--detailed")
    out = capsys.readouterr().out
    assert "total_perfis" in out


def test_twofa_reencrypt_secrets_dry_run(capsys):
    _bootstrap_perfis(1)
    call_command("twofa_reencrypt_secrets", "--dry-run", "--unencrypted-only")
    out = capsys.readouterr().out
    # Pode não haver plaintext legacy, mas saída DRY-RUN deve estar presente
    assert "[DRY-RUN]" in out or "Processados" in out

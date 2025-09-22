import importlib

import pytest

pytestmark = [pytest.mark.twofa, pytest.mark.security]


@pytest.mark.django_db
def test_twofa_decrypt_plaintext_legacy(settings):
    settings.TWOFA_FERNET_KEYS = ["LEGACYKEY"]
    from user_management import twofa as twofa_mod

    importlib.reload(twofa_mod)
    legacy_plain = "PLAINSECRET123"  # simulando segredo legado armazenado sem cifrar
    dec = twofa_mod.decrypt_secret(legacy_plain)
    assert dec == legacy_plain  # deve retornar igual sem erro


@pytest.mark.django_db
def test_rate_limit_cache_failure_monkeypatch(settings, monkeypatch):
    from user_management import twofa as twofa_mod

    def boom(*a, **k):
        raise RuntimeError("cache down")

    monkeypatch.setattr("django.core.cache.cache.get", boom)
    # Chamada deve retornar True (fail-open) mesmo com exceção
    ok = twofa_mod.rate_limit_check(1, "127.0.0.1")
    assert ok is True

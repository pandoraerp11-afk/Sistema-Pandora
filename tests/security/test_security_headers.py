import pytest


@pytest.mark.security
def test_security_headers_applied_when_debug_false(client, settings):
    settings.DEBUG = False
    resp = client.get("/")  # rota root (pode ser 200 ou 302, interessa headers)
    # Cabeçalhos esperados (alguns podem faltar se middleware não configurado; teste mínimo)
    expected = [
        # HSTS pode não estar presente em ambiente de teste sem HTTPS; validar apenas se existir
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
    ]
    optional = [("Strict-Transport-Security", "max-age=")]
    missing = []
    for header, fragment in expected:
        val = resp.headers.get(header)
        if not val or fragment.lower() not in val.lower():
            missing.append(header)
    assert not missing, f"Headers de segurança ausentes ou incompletos: {missing}"
    # Apenas log se HSTS ausente
    for h, frag in optional:
        val = resp.headers.get(h)
        if not val or frag.lower() not in val.lower():
            # não falhar
            pass

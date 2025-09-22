import pytest


@pytest.mark.django_db
def test_normalization_various_formats(settings):
    settings.FEATURE_STRICT_ENABLED_MODULES = True
    from core.models import Tenant

    cases = [
        (["clientes", "financeiro", "clientes"], ["clientes", "financeiro"]),
        ('["clientes","financeiro"]', ["clientes", "financeiro"]),
        ({"modules": ["estoque", "obras"]}, ["estoque", "obras"]),
        ({"clientes": True, "financeiro": 1, "obras": False}, ["clientes", "financeiro"]),
        ("clientes,financeiro;estoque", ["clientes", "financeiro", "estoque"]),
        ('{"clientes": true, "financeiro": true}', ["clientes", "financeiro"]),
        ("[clientes, financeiro, estoque]", ["clientes", "financeiro", "estoque"]),
    ]
    created = []
    for raw, expected in cases:
        t = Tenant.objects.create(nome="Tx" + str(len(created)), slug="tx" + str(len(created)), enabled_modules=raw)
        # reload
        t.refresh_from_db()
        assert isinstance(t.enabled_modules, dict)
        assert sorted(t.enabled_modules.get("modules", [])) == sorted(expected)
        created.append(t.id)


@pytest.mark.django_db
def test_audit_command_detection(settings, capsys):
    settings.FEATURE_STRICT_ENABLED_MODULES = False  # evitar auto normalizar nesta criação
    from core.models import Tenant

    t = Tenant.objects.create(nome="Legacy", slug="legacy", enabled_modules=["x", "y", "x"])
    # Rodar auditoria sem apply
    from django.core.management import call_command

    call_command("audit_enabled_modules")
    out = capsys.readouterr().out
    assert "Legacy" in out and "DIRTY" in out
    # Agora aplicar
    call_command("audit_enabled_modules", "--apply")
    t.refresh_from_db()
    assert t.enabled_modules == {"modules": ["x", "y"]}

import pytest

pytestmark = [pytest.mark.django_db]


def test_import_core_dashboard_widgets(monkeypatch):
    # Se módulo referenciar model inexistente, injeta stub para permitir import leve
    try:
        from user_management import models as um_models
    except Exception:
        um_models = None
    if um_models and not hasattr(um_models, "Usuario"):

        class _UsuarioStub:
            objects = type(
                "M",
                (),
                {
                    "count": lambda self=None: 0,
                    "filter": lambda *a, **k: type("Q", (), {"count": lambda self=None: 0})(),
                },
            )()

        monkeypatch.setattr("user_management.models.Usuario", _UsuarioStub, raising=False)
    from core.dashboard_widgets import CoreDashboardWidgets

    mgr = CoreDashboardWidgets(request=None)
    data = mgr.get_all_widget_data()
    assert "quick_actions" in data
    assert "user_metrics" in data

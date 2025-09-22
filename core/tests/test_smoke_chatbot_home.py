import pytest

pytestmark = [pytest.mark.django_db]


def test_chatbot_instantiation_and_simple_process(tmp_path, monkeypatch):
    from core.chatbot import PandoraChatbot

    # Cria config mínima
    cfg = tmp_path / "chatbot_config.json"
    cfg.write_text('{"model_type":"local","model_name":"mini"}', encoding="utf-8")
    bot = PandoraChatbot(str(cfg))

    # Monkeypatch método local para resposta determinística
    def _fake_local(self, msg):
        return f"ECO:{msg[:10]}"

    monkeypatch.setattr(PandoraChatbot, "_generate_local_response", _fake_local)
    resp = bot.process_message("Olá sistema", user_id="u1")
    assert resp.startswith("ECO:")
    assert bot.conversation_history[-1]["content"] == resp


def test_home_system_metrics_empty_ok():
    from core.home_system import CoreHomeSystem

    hs = CoreHomeSystem()
    ctx = hs.get_home_context()
    # Deve possuir chaves básicas mesmo sem registros
    assert {"total_tenants", "active_tenants", "mrr_value"} <= set(ctx.keys())

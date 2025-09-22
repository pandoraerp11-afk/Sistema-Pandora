import contextlib

from .models import Agendamento

try:
    from notifications.views import criar_notificacao
except Exception:

    def criar_notificacao(*args, **kwargs):
        return None


def notificar_profissional_e_clientes(
    agendamento: Agendamento, *, titulo_prof, msg_prof, titulo_cli=None, msg_cli=None, tipo="info"
):
    """Helper DRY para disparar notificações relacionadas a um agendamento.
    titulo_cli/msg_cli se não informados reutilizam titulo_prof/msg_prof.
    """
    try:
        # Profissional
        criar_notificacao(
            tenant=agendamento.tenant,
            usuario_destinatario=agendamento.profissional,
            titulo=titulo_prof,
            mensagem=msg_prof,
            tipo=tipo,
            modulo_origem="agendamentos",
            objeto_relacionado=agendamento,
        )
        # Clientes (acessos portal)
        for ac in getattr(agendamento.cliente, "acessos", []).all() if hasattr(agendamento.cliente, "acessos") else []:
            with contextlib.suppress(Exception):
                criar_notificacao(
                    tenant=agendamento.tenant,
                    usuario_destinatario=ac.usuario,
                    titulo=titulo_cli or titulo_prof,
                    mensagem=msg_cli or msg_prof,
                    tipo=tipo,
                    modulo_origem="agendamentos",
                    objeto_relacionado=agendamento,
                )
    except Exception:
        pass

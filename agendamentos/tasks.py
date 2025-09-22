import contextlib
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Agendamento, AuditoriaAgendamento

try:
    from notifications.views import criar_notificacao
except Exception:

    def criar_notificacao(*args, **kwargs):
        return None


@shared_task
def marcar_no_show_agendamentos(grace_minutes=15):
    """Marca como NO_SHOW agendamentos PENDENTE cujo horário iniciou há mais de grace_minutes."""
    now = timezone.now() - timedelta(minutes=grace_minutes)
    qs = Agendamento.objects.filter(status="PENDENTE", data_inicio__lt=now)
    total = 0
    for ag in qs.select_related("tenant", "profissional"):
        antigo = ag.status
        ag.status = "NO_SHOW"
        ag.save(update_fields=["status", "updated_at"])
        AuditoriaAgendamento.objects.create(
            agendamento=ag,
            user=None,
            tipo_evento="NO_SHOW_AUTO",
            de_status=antigo,
            para_status="NO_SHOW",
            motivo=f"Automático (grace {grace_minutes}m)",
        )
        try:
            criar_notificacao(
                tenant=ag.tenant,
                usuario_destinatario=ag.profissional,
                titulo="No-Show Detectado",
                mensagem=f"Agendamento #{ag.id} marcado como NO_SHOW.",
                tipo="warning",
                modulo_origem="agendamentos",
                objeto_relacionado=ag,
            )
            for ac in getattr(ag.cliente, "acessos", []).all() if hasattr(ag.cliente, "acessos") else []:
                with contextlib.suppress(Exception):
                    criar_notificacao(
                        tenant=ag.tenant,
                        usuario_destinatario=ac.usuario,
                        titulo="Você não compareceu",
                        mensagem=f"Seu agendamento #{ag.id} foi marcado como não comparecido. Entre em contato para reagendar.",
                        tipo="warning",
                        modulo_origem="agendamentos",
                        objeto_relacionado=ag,
                    )
        except Exception:
            pass
        total += 1
    return total

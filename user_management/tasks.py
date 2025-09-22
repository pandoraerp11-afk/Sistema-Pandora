"""Tarefas Celery de manutenção para user_management.
Separadas para permitir agendamento via CELERY_BEAT_SCHEDULE.
"""

from celery import shared_task

from user_management.signals import desbloquear_usuarios, limpar_logs_antigos, limpar_sessoes_expiradas


def _safe_exec(fn, label):  # pequena ajuda para logging mínimo sem depender de infra
    try:
        return fn()
    except Exception as e:  # pragma: no cover (apenas proteção)
        print(f"[user_management.tasks] ERRO {label}: {e}")
        return None


@shared_task
def desbloquear_usuarios_periodico():
    qtd = _safe_exec(desbloquear_usuarios, "desbloquear_usuarios")
    return qtd


@shared_task
def limpar_sessoes_expiradas_periodico():
    _safe_exec(limpar_sessoes_expiradas, "limpar_sessoes_expiradas")
    return True


@shared_task
def limpar_logs_antigos_periodico(dias: int = 90):
    _safe_exec(lambda: limpar_logs_antigos(dias=dias), "limpar_logs_antigos")
    return True

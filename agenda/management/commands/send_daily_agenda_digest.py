"""Comando para enviar um digest diário por e-mail com eventos do dia."""

import logging
from argparse import ArgumentParser
from datetime import date

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.utils import timezone

from agenda.models import AgendaConfiguracao, Evento
from core.models import Tenant

LOGGER = logging.getLogger(__name__)


def _get_agenda_config(tenant: Tenant) -> AgendaConfiguracao:
    """Obtém (ou cria) a configuração de agenda para o tenant."""
    try:
        return tenant.agenda_config
    except AgendaConfiguracao.DoesNotExist:
        return AgendaConfiguracao.objects.create(tenant=tenant, lembretes_padrao=[1440, 120, 15])


def _should_send_digest(cfg: AgendaConfiguracao, hour: int) -> bool:
    """Indica se o digest está habilitado e programado para a hora atual."""
    return bool(cfg.digest_email_habilitado and cfg.digest_email_hora == hour)


def _eventos_do_dia(tenant: Tenant, ref_date: date) -> QuerySet[Evento]:
    """Retorna eventos do dia de referência para o tenant ordenados por início."""
    return Evento.objects.filter(tenant=tenant, data_inicio__date=ref_date).order_by("data_inicio")


def _usuarios_dos_eventos(eventos: QuerySet[Evento]) -> set[int]:
    """Coleta IDs de usuários (responsáveis e participantes) dos eventos."""
    usuarios: set[int] = set(eventos.exclude(responsavel=None).values_list("responsavel_id", flat=True))
    for ev in eventos:
        usuarios.update(list(ev.participantes.values_list("id", flat=True)))
    return usuarios


def _eventos_do_usuario(eventos: QuerySet[Evento], uid: int) -> list[Evento]:
    """Filtra os eventos pertencentes a um usuário (responsável ou participante)."""
    evs_user: list[Evento] = []
    for ev in eventos:
        if ev.responsavel_id == uid:
            evs_user.append(ev)
            continue
        if uid in ev.participantes.values_list("id", flat=True):
            evs_user.append(ev)
    return evs_user


def _render_digest_html(context: dict) -> str | None:
    """Renderiza HTML do digest; em falha, loga e retorna None."""
    try:
        return render_to_string("agenda/emails/digest_diario.html", context)
    except Exception:
        LOGGER.exception("Falha ao renderizar template do digest diário.")
        return None


def _send_digest_email(
    subject: str,
    text: str,
    html: str | None,
    from_email: str | None,
    to: str,
) -> bool:
    """Envia e-mail do digest e retorna True em sucesso; loga falhas."""
    try:
        send_mail(
            subject=subject,
            message=text,
            html_message=html,
            from_email=from_email,
            recipient_list=[to],
            fail_silently=True,
        )
    except Exception:
        LOGGER.exception("Falha ao enviar e-mail de digest diário para %s.", to)
        return False
    else:
        return True


class Command(BaseCommand):
    """Envia o digest diário de eventos por e-mail."""

    help = "Envia um digest diário por e-mail com os eventos do dia para cada usuário do tenant (se habilitado)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Adiciona argumentos CLI ao comando."""
        parser.add_argument("--hour", type=int, help="Força a execução como se fosse esta hora (0-23)")

    def handle(self, *_args: object, **_options: object) -> None:
        """Executa o envio do digest diário conforme configuração por tenant."""
        now = timezone.now()
        hora_opt = _options.get("hour")
        hora_atual: int = hora_opt if isinstance(hora_opt, int) else now.hour

        enviados_total = 0
        for tenant in Tenant.objects.all():
            cfg = _get_agenda_config(tenant)

            if not _should_send_digest(cfg, hora_atual):
                continue

            hoje = now.date()
            eventos_hoje = _eventos_do_dia(tenant, hoje)
            if not eventos_hoje.exists():
                continue

            # Agrupar por usuário (responsável e participantes)
            usuarios = _usuarios_dos_eventos(eventos_hoje)

            if not usuarios:
                continue

            user_model = get_user_model()
            for uid in usuarios:
                try:
                    user = user_model.objects.get(id=uid)
                except user_model.DoesNotExist:
                    continue

                if not getattr(user, "email", None):
                    continue

                evs_user = _eventos_do_usuario(eventos_hoje, uid)

                if not evs_user:
                    continue

                context = {
                    "tenant": tenant,
                    "usuario": user,
                    "data_referencia": hoje,
                    "eventos": evs_user,
                }

                subject = f"Agenda do dia - {getattr(tenant, 'name', str(tenant))}"
                html = _render_digest_html(context)
                text = "\n".join([f"- {ev.titulo} às {ev.data_inicio.strftime('%H:%M')}" for ev in evs_user])

                ok = _send_digest_email(
                    subject=subject,
                    text=text,
                    html=html,
                    from_email=getattr(tenant, "email_from_address", None) or None,
                    to=user.email,
                )
                if ok:
                    enviados_total += 1

        self.stdout.write(self.style.SUCCESS(f"Digest diário enviado para {enviados_total} destinatários"))

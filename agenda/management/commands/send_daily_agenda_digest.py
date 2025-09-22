from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from agenda.models import AgendaConfiguracao, Evento
from core.models import Tenant


class Command(BaseCommand):
    help = "Envia um digest diário por e-mail com os eventos do dia para cada usuário do tenant (se habilitado)."

    def add_arguments(self, parser):
        parser.add_argument("--hour", type=int, help="Força a execução como se fosse esta hora (0-23)")

    def handle(self, *args, **options):
        now = timezone.now()
        hora_atual = options.get("hour") if options.get("hour") is not None else now.hour

        enviados_total = 0
        for tenant in Tenant.objects.all():
            try:
                cfg = tenant.agenda_config
            except AgendaConfiguracao.DoesNotExist:
                cfg = AgendaConfiguracao.objects.create(tenant=tenant, lembretes_padrao=[1440, 120, 15])

            if not cfg.digest_email_habilitado or cfg.digest_email_hora != hora_atual:
                continue

            hoje = now.date()
            eventos_hoje = Evento.objects.filter(tenant=tenant, data_inicio__date=hoje).order_by("data_inicio")
            if not eventos_hoje.exists():
                continue

            # Agrupar por usuário (responsável e participantes)
            usuarios = set(eventos_hoje.exclude(responsavel=None).values_list("responsavel_id", flat=True))
            for ev in eventos_hoje:
                usuarios.update(list(ev.participantes.values_list("id", flat=True)))

            if not usuarios:
                continue

            for uid in usuarios:
                user = None
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    user = User.objects.get(id=uid)
                except User.DoesNotExist:
                    continue

                if not getattr(user, "email", None):
                    continue

                evs_user = []
                for ev in eventos_hoje:
                    if ev.responsavel_id == uid:
                        evs_user.append(ev)
                        continue
                    if uid in ev.participantes.values_list("id", flat=True):
                        evs_user.append(ev)

                if not evs_user:
                    continue

                context = {
                    "tenant": tenant,
                    "usuario": user,
                    "data_referencia": hoje,
                    "eventos": evs_user,
                }

                subject = f"Agenda do dia - {getattr(tenant, 'name', str(tenant))}"
                try:
                    html = render_to_string("agenda/emails/digest_diario.html", context)
                except Exception:
                    html = None
                text = "\n".join([f"- {ev.titulo} às {ev.data_inicio.strftime('%H:%M')}" for ev in evs_user])

                try:
                    send_mail(
                        subject=subject,
                        message=text,
                        html_message=html,
                        from_email=getattr(tenant, "email_from_address", None) or None,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                    enviados_total += 1
                except Exception:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Digest diário enviado para {enviados_total} destinatários"))

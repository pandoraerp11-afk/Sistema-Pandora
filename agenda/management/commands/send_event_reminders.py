from django.core.management.base import BaseCommand
from django.utils import timezone

from agenda.models import Evento, EventoLembrete
from notifications.models import Notification


class Command(BaseCommand):
    help = "Envia notificações de lembrete para eventos próximos"

    def add_arguments(self, parser):
        parser.add_argument("--window", type=int, default=5, help="Janela de execução em minutos (default: 5)")

    def handle(self, *args, **options):
        window = options["window"]
        now = timezone.now()
        # Considera eventos com início futuro e lembretes que caem na janela [now, now+window]
        upcoming = Evento.objects.filter(data_inicio__gte=now, status__in=["pendente", "confirmado"])

        count = 0
        for ev in upcoming:
            delta = ev.data_inicio - now
            minutes_to_start = int(delta.total_seconds() // 60)
            if minutes_to_start < 0:
                continue

            lembretes = EventoLembrete.objects.filter(
                evento=ev,
                ativo=True,
                minutos_antes__gte=minutes_to_start - window,
                minutos_antes__lte=minutes_to_start + window,
            )
            if not lembretes.exists():
                continue

            # Notificar responsável e participantes que tenham lembrete configurado
            usuarios = set()
            for lemb in lembretes:
                usuarios.add(lemb.usuario_id)

            if ev.responsavel_id in usuarios:
                titulo = f"Lembrete: {ev.titulo} em {minutes_to_start} min"
                self._notify(ev, ev.responsavel, titulo)
                count += 1

            part_ids = set(ev.participantes.values_list("id", flat=True))
            for uid in usuarios.intersection(part_ids):
                if ev.responsavel_id and uid == ev.responsavel_id:
                    continue
                user = ev.participantes.model.objects.get(id=uid)
                titulo = f"Lembrete: {ev.titulo} em {minutes_to_start} min"
                self._notify(ev, user, titulo)
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Lembretes enviados: {count}"))

    def _notify(self, evento, usuario, titulo):
        Notification.objects.create(
            tenant=evento.tenant,
            usuario_destinatario=usuario,
            titulo=titulo,
            mensagem=f"Evento às {evento.data_inicio.strftime('%H:%M')} no dia {evento.data_inicio.strftime('%d/%m/%Y')}.",
            tipo="alert",
            prioridade="alta",
            modulo_origem="agenda",
            evento_origem="lembrete_evento",
            url_acao=f"/agenda/evento/{evento.id}/",
            dados_extras={
                "evento_id": evento.id,
                "tipo": "lembrete",
            },
        )

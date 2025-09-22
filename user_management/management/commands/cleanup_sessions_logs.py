from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from user_management.models import LogAtividadeUsuario, SessaoUsuario


class Command(BaseCommand):
    help = "Limpa sessões expiradas e logs antigos de atividade."

    def add_arguments(self, parser):
        parser.add_argument("--logs-days", type=int, default=90, help="Dias de retenção de logs (default: 90)")
        parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria removido sem executar")

    def handle(self, *args, **options):
        logs_days = options["logs_days"]
        dry = options["dry_run"]
        now = timezone.now()

        # Sessões expiradas (modelo Django)
        expired_sessions = Session.objects.filter(expire_date__lt=now)
        expired_keys = list(expired_sessions.values_list("session_key", flat=True))
        # Correspondentes no modelo estendido
        qs_sessoes = SessaoUsuario.objects.filter(session_key__in=expired_keys, ativa=True)
        count_sessoes_update = qs_sessoes.count()

        # Logs antigos
        limite_logs = now - timezone.timedelta(days=logs_days)
        qs_logs = LogAtividadeUsuario.objects.filter(timestamp__lt=limite_logs)
        count_logs_delete = qs_logs.count()

        if dry:
            self.stdout.write(f"[DRY-RUN] Sessões expiradas a desativar: {count_sessoes_update}")
            self.stdout.write(f"[DRY-RUN] Logs a remover (> {logs_days} dias): {count_logs_delete}")
            return

        # Executa
        if count_sessoes_update:
            qs_sessoes.update(ativa=False)
        expired_sessions.delete()
        if count_logs_delete:
            qs_logs.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Sessões desativadas: {count_sessoes_update} | Logs removidos: {count_logs_delete}")
        )

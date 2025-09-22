from django.core.management.base import BaseCommand

from user_management.models import PerfilUsuarioEstendido
from user_management.services.twofa_service import _decrypt_secret, _encrypt_secret


class Command(BaseCommand):
    help = "Recriptografa segredos TOTP existentes conforme chaves TWOFA_FERNET_KEYS (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Apenas contabiliza quantos seriam migrados.")
        parser.add_argument("--force", action="store_true", help="Força recriptografia mesmo já marcado como cifrado.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        force = options["force"]
        qs = PerfilUsuarioEstendido.objects.exclude(totp_secret__isnull=True).exclude(totp_secret="")
        total = qs.count()
        migrated = 0
        for perf in qs.iterator():
            try:
                if perf.twofa_secret_encrypted and not force:
                    continue
                plain = _decrypt_secret(perf.totp_secret)
                enc = _encrypt_secret(plain)
                if enc != perf.totp_secret or force:
                    migrated += 1
                    if not dry:
                        perf.totp_secret = enc
                        perf.twofa_secret_encrypted = True
                        perf.save(update_fields=["totp_secret", "twofa_secret_encrypted"])
            except Exception:
                self.stderr.write(f"Falha ao migrar perfil {perf.pk}")
        self.stdout.write(f"Perfis com segredo: {total}")
        self.stdout.write(f"Migrados: {migrated}{' (dry-run)' if dry else ''}")

from django.core.management.base import BaseCommand

from user_management.models import PerfilUsuarioEstendido
from user_management.twofa import decrypt_secret, encrypt_secret


class Command(BaseCommand):
    help = "Recriptografa todos os segredos TOTP usando a chave Fernet primária atual. Pode também cifrar legados em claro."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria feito.")
        parser.add_argument("--limit", type=int, help="Limitar quantidade de perfis processados.")
        parser.add_argument(
            "--unencrypted-only", action="store_true", help="Somente perfis ainda não marcados como criptografados."
        )

    def handle(self, *args, **options):
        qs = PerfilUsuarioEstendido.objects.exclude(totp_secret__isnull=True).exclude(totp_secret="")
        if options["unencrypted_only"]:
            qs = qs.filter(twofa_secret_encrypted=False)
        total = qs.count()
        if options.get("limit"):
            qs = qs.order_by("id")[: options["limit"]]
        to_process = qs.count()
        changed = 0
        plain_legacy = 0
        for perfil in qs.iterator():
            secret_enc = perfil.totp_secret
            if not perfil.twofa_secret_encrypted:
                # plaintext legado
                plain_legacy += 1
                plain = secret_enc
            else:
                # já cifrado -> decriptar e recifrar para chave primária
                plain = decrypt_secret(secret_enc)
            new_cipher = encrypt_secret(plain)
            if options["dry_run"]:
                continue
            perfil.totp_secret = new_cipher
            perfil.twofa_secret_encrypted = True
            perfil.save(update_fields=["totp_secret", "twofa_secret_encrypted"])
            changed += 1
        if options["dry_run"]:
            self.stdout.write(
                f"[DRY-RUN] Perfis elegíveis: {total}, processados (após filtros/limit): {to_process}, legacy plaintext: {plain_legacy}"
            )
        else:
            self.stdout.write(
                f"Recriptografia concluída. Processados: {to_process}, alterados: {changed}, legacy plaintext: {plain_legacy}"
            )

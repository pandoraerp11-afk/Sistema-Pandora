import hashlib

from django.core.management.base import BaseCommand

from estoque.models import LogAuditoriaEstoque


class Command(BaseCommand):
    help = "Verifica integridade da cadeia hash de auditoria de movimentos de estoque."

    def handle(self, *args, **options):
        anterior_hash = None
        corrompidos = []
        for log in LogAuditoriaEstoque.objects.order_by("id"):
            base_string = (anterior_hash or "") + repr(log.snapshot_depois)
            recalculado = hashlib.sha256(base_string.encode("utf-8")).hexdigest()
            if recalculado != log.hash_atual:
                corrompidos.append(log.id)
            anterior_hash = log.hash_atual
        if corrompidos:
            self.stdout.write(self.style.ERROR(f"Corrupção detectada nos logs: {corrompidos}"))
        else:
            self.stdout.write(self.style.SUCCESS("Cadeia de auditoria íntegra."))

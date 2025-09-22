from django.core.management.base import BaseCommand
from django.db import transaction

from agenda.models import Evento


class Command(BaseCommand):
    help = "Migra eventos com tipo_evento='procedimento' para 'servico' (quando seguro)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Apenas exibe o que seria migrado")
        parser.add_argument("--tenant-id", type=int, help="Opcional: limitar a um tenant específico")

    def handle(self, *args, **options):
        dry = options.get("dry_run")
        tenant_id = options.get("tenant_id")
        qs = Evento.objects.filter(tipo_evento="procedimento")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhum evento legado encontrado."))
            return
        self.stdout.write(f"Encontrados {total} eventos com tipo_evento='procedimento'.")
        if dry:
            for ev in qs[:25]:
                self.stdout.write(f"- {ev.id} | {ev.titulo} | {ev.data_inicio}")
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração aplicada."))
            return
        with transaction.atomic():
            updated = qs.update(tipo_evento="servico")
        self.stdout.write(self.style.SUCCESS(f"Atualizados {updated} eventos para tipo_evento='servico'."))

from django.core.management.base import BaseCommand
from django.db import transaction

from agendamentos.models import Agendamento, AuditoriaAgendamento, Disponibilidade, Slot
from agendamentos.models_mapping import SlotLegacyMap


class Command(BaseCommand):
    help = "Rollback seguro: remove agendamentos beta e mapeamentos sem tocar nos atendimentos clínicos."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--tenant-id", type=int, help="Limitar a um tenant específico")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        tenant_id = options.get("tenant_id")
        filtro = {}
        if tenant_id:
            filtro["tenant_id"] = tenant_id
        ag_qs = Agendamento.objects.filter(**filtro)
        self.stdout.write(f"Agendamentos encontrados: {ag_qs.count()}")
        with transaction.atomic():
            AuditoriaAgendamento.objects.filter(agendamento__in=ag_qs).delete()
            SlotLegacyMap.objects.filter(tenant_id=tenant_id) if tenant_id else SlotLegacyMap.objects.all().delete()
            Slot.objects.filter(**filtro).delete()
            Disponibilidade.objects.filter(**filtro).delete()
            ag_qs.delete()
            if dry:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(f"Rollback concluído (dry_run={dry})"))

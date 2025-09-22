from django.core.management.base import BaseCommand
from django.db.models import Count

from agendamentos.models import Agendamento


class Command(BaseCommand):
    help = "Audita valores distintos de tipo_servico ainda presentes e contagem de agendamentos sem procedimento."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Limite de exemplos por valor para exibir")
        parser.add_argument("--tenant", type=int, help="Filtrar por tenant id específico")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant")
        qs = Agendamento.objects.all()
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        sem_procedimento = qs.filter(procedimento__isnull=True)
        self.stdout.write(self.style.MIGRATE_HEADING("== Agendamentos sem procedimento =="))
        self.stdout.write(f"Total: {sem_procedimento.count()}")
        valores = sem_procedimento.exclude(tipo_servico__isnull=True).exclude(tipo_servico__exact="")
        self.stdout.write(self.style.MIGRATE_HEADING("== Valores distintos tipo_servico (sem procedimento) =="))
        for row in valores.values("tipo_servico").annotate(total=Count("id")).order_by("-total"):
            self.stdout.write(f"{row['tipo_servico']}: {row['total']}")
        # Amostragens opcionais
        limit = options["limit"]
        self.stdout.write(self.style.MIGRATE_HEADING("== Exemplos por valor =="))
        for valor in valores.values_list("tipo_servico", flat=True).distinct()[:25]:
            sample_ids = list(valores.filter(tipo_servico=valor).values_list("id", flat=True)[:limit])
            self.stdout.write(f"{valor}: ids={sample_ids}")
        self.stdout.write(self.style.SUCCESS("Auditoria concluída."))

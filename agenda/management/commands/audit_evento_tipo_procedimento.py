from django.core.management.base import BaseCommand
from django.db.models import Count

from agenda.models import Evento


class Command(BaseCommand):
    help = "Audita ocorrências de eventos com tipo_evento='procedimento' e sugere janela para remoção do choice legado."

    def handle(self, *args, **options):
        total = Evento.objects.filter(tipo_evento="procedimento").count()
        by_tenant = (
            Evento.objects.filter(tipo_evento="procedimento")
            .values("tenant_id")
            .annotate(qtd=Count("id"))
            .order_by("-qtd")
        )
        self.stdout.write(self.style.WARNING("== Auditoria de tipo_evento='procedimento' (LEGADO) =="))
        self.stdout.write(self.style.NOTICE(f"Total: {total}"))
        if total:
            self.stdout.write("Distribuição por tenant (top 20):")
            for row in list(by_tenant)[:20]:
                self.stdout.write(f" - tenant_id={row['tenant_id']}: {row['qtd']}")
            self.stdout.write("")
            self.stdout.write(
                "Ação sugerida: migrar estes eventos para tipo_evento='servico' ou 'atendimento' conforme o caso."
            )
            self.stdout.write(
                "Após 14 dias consecutivos com Total=0, remover o choice legado em agenda.models.Evento.TIPO_EVENTO_CHOICES."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Nenhum evento legado encontrado. É seguro planejar a remoção do choice 'procedimento'."
                )
            )

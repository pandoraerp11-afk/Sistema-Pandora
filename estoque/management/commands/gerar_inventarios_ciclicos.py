from django.core.management.base import BaseCommand
from django.utils import timezone

from estoque.models import InventarioCiclico


class Command(BaseCommand):
    help = "Atualiza proxima_contagem para inventários cíclicos vencidos e marca ultima_contagem."

    def handle(self, *args, **options):
        agora = timezone.now()
        atualizados = 0
        for inv in InventarioCiclico.objects.filter(
            ativo=True, proxima_contagem__isnull=False, proxima_contagem__lt=agora
        ).iterator():
            inv.ultima_contagem = agora
            inv.proxima_contagem = agora + timezone.timedelta(days=inv.periodicidade_dias or 30)
            inv.save(update_fields=["ultima_contagem", "proxima_contagem", "atualizado_em"])
            atualizados += 1
        self.stdout.write(self.style.SUCCESS(f"Inventários atualizados: {atualizados}"))

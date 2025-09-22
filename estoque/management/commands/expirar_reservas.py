from django.core.management.base import BaseCommand
from django.utils import timezone

from estoque.models import ReservaEstoque


class Command(BaseCommand):
    help = "Expira reservas de estoque cujo expira_em passou."

    def handle(self, *args, **options):
        agora = timezone.now()
        qs = ReservaEstoque.objects.filter(status="ATIVA", expira_em__isnull=False, expira_em__lt=agora)
        count = 0
        for r in qs.iterator():
            r.status = "EXPIRADA"
            r.save(update_fields=["status", "atualizado_em"])
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Reservas expiradas: {count}"))

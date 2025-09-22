from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reseta todas as métricas internas do wizard de tenant (in-memory)."

    def handle(self, *args, **options):
        from core.services import wizard_metrics

        wizard_metrics.reset_all_metrics()
        self.stdout.write(self.style.SUCCESS("Wizard metrics reset concluído."))

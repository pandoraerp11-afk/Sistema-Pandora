from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from notifications.models import Notification

try:
    from notifications.models import NotificationAdvanced

    ADV_AVAILABLE = True
except Exception:  # pragma: no cover
    ADV_AVAILABLE = False


class Command(BaseCommand):
    help = "Agrupa/deduplica notificações semelhantes em rajada (simples: agenda; avançadas: mesmo objeto origem)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=3,
            help="Janela em minutos para agrupar notificações semelhantes.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-advanced", action="store_true", help="Não processa notificações avançadas.")

    def handle(self, *args, **opts):
        win = opts["window_minutes"]
        dry = opts["dry_run"]
        process_advanced = (
            not opts.get("no_advanced") and getattr(settings, "USE_ADVANCED_NOTIFICATIONS", True) and ADV_AVAILABLE
        )
        limite = timezone.now() - timedelta(minutes=win)

        # Simples (agenda)
        qs = Notification.objects.filter(modulo_origem="agenda", created_at__gte=limite)
        redundantes_simples = 0
        agrupados_simples = (
            qs.values("usuario_destinatario_id", "dados_extras__evento_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for grupo in agrupados_simples:
            user_id = grupo["usuario_destinatario_id"]
            evento_id = grupo["dados_extras__evento_id"]
            if user_id and evento_id:
                sub = qs.filter(usuario_destinatario_id=user_id, dados_extras__evento_id=evento_id)
                keep = sub.order_by("-created_at").first()
                redundantes = sub.exclude(id=keep.id)
                if not dry:
                    redundantes.update(status="arquivada")
                redundantes_simples += redundantes.count()

        redundantes_adv = 0
        if process_advanced:
            adv_qs = NotificationAdvanced.objects.filter(created_at__gte=limite)
            agrupados = (
                adv_qs.values("tenant_id", "source_module", "source_object_type", "source_object_id", "title")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
            )
            for grupo in agrupados:
                sub = adv_qs.filter(
                    tenant_id=grupo["tenant_id"],
                    source_module=grupo["source_module"],
                    source_object_type=grupo["source_object_type"],
                    source_object_id=grupo["source_object_id"],
                    title=grupo["title"],
                )
                keep = sub.order_by("-created_at").first()
                redundantes = sub.exclude(id=keep.id)
                if not dry:
                    redundantes.update(status="archived")
                redundantes_adv += redundantes.count()

        self.stdout.write(self.style.SUCCESS(f"Redundantes arquivadas simples: {redundantes_simples}"))
        if process_advanced:
            self.stdout.write(self.style.SUCCESS(f"Redundantes arquivadas avançadas: {redundantes_adv}"))
        else:
            self.stdout.write(self.style.WARNING("Avançadas não processadas (flag desativada ou --no-advanced)."))
        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração persistida."))

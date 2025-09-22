from django.core.management.base import BaseCommand
from django.utils import timezone

from shared.services.permission_resolver import permission_resolver
from user_management.models import PermissaoPersonalizada


class Command(BaseCommand):
    help = "Remove PermissaoPersonalizada expirada e invalida cache seletivamente."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        batch = opts["batch"]
        qs = PermissaoPersonalizada.objects.filter(data_expiracao__lt=timezone.now())
        total = qs.count()
        removed = 0
        self.stdout.write(f"Expiradas encontradas: {total}")
        while True:
            chunk = list(qs.order_by("id")[:batch])
            if not chunk:
                break
            ids = [c.id for c in chunk]
            owners = {(c.user_id, c.scope_tenant_id) for c in chunk}
            if not dry:
                PermissaoPersonalizada.objects.filter(id__in=ids).delete()
                for uid, tid in owners:
                    if tid:
                        permission_resolver.invalidate_cache(user_id=uid, tenant_id=tid)
                    else:
                        permission_resolver.invalidate_cache(user_id=uid)
            removed += len(chunk)
            if dry:
                break
        self.stdout.write(f"Removidas: {removed}{' (dry-run)' if dry else ''}")

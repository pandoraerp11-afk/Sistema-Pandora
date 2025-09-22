from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from user_management.models import PerfilUsuarioEstendido


class Command(BaseCommand):
    help = "Gera snapshot das métricas 2FA em stdout; opcionalmente zera contadores (exceto falhas cumulativas)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Zera contadores agregados (success, failure, recovery, rate limit) para todos os perfis.",
        )
        parser.add_argument(
            "--include-ip-blocks", action="store_true", help="Inclui métrica de bloqueios globais de IP (cache)."
        )

    def handle(self, *args, **options):
        agg = PerfilUsuarioEstendido.objects.aggregate(
            total=Count("id"),
            habilitados=Count("id", filter=Q(autenticacao_dois_fatores=True)),
            confirmados=Count("id", filter=Q(totp_confirmed_at__isnull=False)),
            sucessos=Sum("twofa_success_count"),
            falhas=Sum("twofa_failure_count"),
            recovery=Sum("twofa_recovery_use_count"),
            rl_blocks=Sum("twofa_rate_limit_block_count"),
        )
        for k, v in list(agg.items()):
            agg[k] = int(v or 0)
        if options.get("include_ip_blocks"):
            agg["ip_blocks"] = int(cache.get("twofa_global_ip_block_metric", 0) or 0)
        self.stdout.write(self.style.SUCCESS(f"SNAPSHOT_2FA {agg}"))
        if options.get("reset"):
            updated = PerfilUsuarioEstendido.objects.update(
                twofa_success_count=0,
                twofa_failure_count=0,
                twofa_recovery_use_count=0,
                twofa_rate_limit_block_count=0,
            )
            cache.delete("twofa_global_ip_block_metric")
            self.stdout.write(self.style.WARNING(f"Counters reset para {updated} perfis."))

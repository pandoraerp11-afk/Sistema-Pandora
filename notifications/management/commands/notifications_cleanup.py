from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import (
    ConfiguracaoNotificacao,
    Notification,
)

try:
    from notifications.models import NotificationAdvanced, TenantNotificationSettings

    ADV_AVAILABLE = True
except Exception:  # pragma: no cover
    ADV_AVAILABLE = False


class Command(BaseCommand):
    help = "Expira e limpa notificações antigas (simples e avançadas) conforme configurações por tenant"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria feito sem aplicar mudanças.")
        parser.add_argument("--days-expire", type=int, help="Força dias padrão para expiração (override).")
        parser.add_argument("--delete-archived-after", type=int, help="Força dias para remoção de arquivadas.")
        parser.add_argument("--no-advanced", action="store_true", help="Não processa notificações avançadas.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        process_advanced = (
            not options.get("no_advanced") and getattr(settings, "USE_ADVANCED_NOTIFICATIONS", True) and ADV_AVAILABLE
        )
        now = timezone.now()
        expired_simple = archived_deleted_simple = lidas_deleted_simple = 0
        expired_adv = archived_deleted_adv = read_deleted_adv = 0

        # Processa notificações simples (legacy)
        for cfg in ConfiguracaoNotificacao.objects.select_related("tenant"):
            expire_days = options.get("days_expire") or cfg.dias_expiracao_padrao
            retention_lidas = cfg.dias_retencao_lidas
            retention_arquivadas = options.get("delete_archived_after") or cfg.dias_retencao_arquivadas

            limite_expira = now - timedelta(days=expire_days)
            limite_lidas = now - timedelta(days=retention_lidas)
            limite_arquivadas = now - timedelta(days=retention_arquivadas)

            # Expirar
            qs_expira = Notification.objects.filter(
                tenant=cfg.tenant, status__in=["nao_lida", "lida"], created_at__lt=limite_expira
            )
            if not dry:
                for n in qs_expira.iterator():
                    if n.status != "expirada":
                        n.status = "expirada"
                        n.save(update_fields=["status"])
                        expired_simple += 1
            else:
                expired_simple += qs_expira.count()

            # Deletar lidas antigas
            qs_lidas_del = Notification.objects.filter(tenant=cfg.tenant, status="lida", created_at__lt=limite_lidas)
            if not dry:
                lidas_deleted_simple += qs_lidas_del.delete()[0]
            else:
                lidas_deleted_simple += qs_lidas_del.count()

            # Deletar arquivadas antigas
            qs_arq_del = Notification.objects.filter(
                tenant=cfg.tenant, status="arquivada", created_at__lt=limite_arquivadas
            )
            if not dry:
                archived_deleted_simple += qs_arq_del.delete()[0]
            else:
                archived_deleted_simple += qs_arq_del.count()

        # Processa notificações avançadas
        if process_advanced:
            for tset in TenantNotificationSettings.objects.select_related("tenant"):
                expire_days_adv = options.get("days_expire") or tset.notification_retention_days
                # Reutiliza retenções das simples se existirem config legacy, senão usa fracionamento padrão
                cfg_legacy = getattr(tset.tenant, "configuracao_notificacao", None)
                retention_read = cfg_legacy.dias_retencao_lidas if cfg_legacy else min(expire_days_adv, 90)
                retention_archived = options.get("delete_archived_after") or (
                    cfg_legacy.dias_retencao_arquivadas if cfg_legacy else expire_days_adv
                )

                limite_expira_adv = now - timedelta(days=expire_days_adv)
                limite_read_adv = now - timedelta(days=retention_read)
                limite_archived_adv = now - timedelta(days=retention_archived)

                # Expirar avançadas (status != expired / archived)
                qs_adv_expira = NotificationAdvanced.objects.filter(
                    tenant=tset.tenant, status__in=["pending", "sent", "delivered"], created_at__lt=limite_expira_adv
                )
                if not dry:
                    for n in qs_adv_expira.iterator():
                        if n.status != "expired":
                            n.status = "expired"
                            n.save(update_fields=["status"])
                            expired_adv += 1
                else:
                    expired_adv += qs_adv_expira.count()

                # Deletar lidas antigas (status read ou read_date < limite)
                qs_adv_read_del = NotificationAdvanced.objects.filter(
                    tenant=tset.tenant, status="read", read_date__lt=limite_read_adv
                )
                if not dry:
                    read_deleted_adv += qs_adv_read_del.delete()[0]
                else:
                    read_deleted_adv += qs_adv_read_del.count()

                # Deletar arquivadas antigas
                qs_adv_archived_del = NotificationAdvanced.objects.filter(
                    tenant=tset.tenant, status="archived", created_at__lt=limite_archived_adv
                )
                if not dry:
                    archived_deleted_adv += qs_adv_archived_del.delete()[0]
                else:
                    archived_deleted_adv += qs_adv_archived_del.count()

        # Saída
        self.stdout.write(
            self.style.SUCCESS(
                f"[Simples] Expiradas: {expired_simple} | Lidas removidas: {lidas_deleted_simple} | Arquivadas removidas: {archived_deleted_simple}"
            )
        )
        if process_advanced:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[Avançadas] Expiradas: {expired_adv} | Lidas removidas: {read_deleted_adv} | Arquivadas removidas: {archived_deleted_adv}"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Avançadas não processadas (flag desativada ou --no-advanced)."))
        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração persistida."))

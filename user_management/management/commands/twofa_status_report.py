import json

from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from user_management.models import PerfilUsuarioEstendido


class Command(BaseCommand):
    help = "Gera relatório de status do 2FA (totp configurado, confirmado, criptografado, lockouts etc). Use --json para saída JSON."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída em JSON")
        parser.add_argument("--detailed", action="store_true", help="Lista usuários em anomalia")

    def handle(self, *args, **options):
        qs = PerfilUsuarioEstendido.objects.select_related("user")
        total_perfis = qs.count()
        ativos = qs.filter(totp_secret__isnull=False).count()
        confirmados = qs.filter(totp_confirmed_at__isnull=False).count()
        criptografados = qs.filter(totp_secret__isnull=False, twofa_secret_encrypted=True).count()
        lockados = qs.filter(twofa_locked_until__gt=timezone.now()).count()
        total_sucessos = qs.aggregate(models.Sum("twofa_success_count"))["twofa_success_count__sum"] or 0
        total_falhas = qs.aggregate(models.Sum("twofa_failure_count"))["twofa_failure_count__sum"] or 0
        total_recovery = qs.aggregate(models.Sum("twofa_recovery_use_count"))["twofa_recovery_use_count__sum"] or 0
        sem_confirmar = ativos - confirmados
        porcent_confirmados = (confirmados / total_perfis * 100) if total_perfis else 0
        porcent_criptografados = (criptografados / ativos * 100) if ativos else 0
        expirando_lock = list(
            qs.filter(twofa_locked_until__gt=timezone.now()).values_list("user__username", "twofa_locked_until")
        )

        data = {
            "total_perfis": total_perfis,
            "com_totp": ativos,
            "confirmados": confirmados,
            "sem_confirmar": sem_confirmar,
            "criptografados": criptografados,
            "lockados": lockados,
            "porcent_confirmados": round(porcent_confirmados, 2),
            "porcent_criptografados": round(porcent_criptografados, 2),
            "lockouts_ativos": [{"username": u, "locked_until": lu.isoformat()} for u, lu in expirando_lock],
            "total_sucessos": total_sucessos,
            "total_falhas": total_falhas,
            "total_recovery_usos": total_recovery,
        }

        if options["detailed"]:
            anomalias = []
            for perfil in qs:
                if perfil.totp_secret and not perfil.totp_confirmed_at:
                    anomalias.append({"username": perfil.user.username, "issue": "NAO_CONFIRMADO"})
                if perfil.totp_secret and not perfil.twofa_secret_encrypted:
                    anomalias.append({"username": perfil.user.username, "issue": "NAO_CRIPTOGRAFADO"})
            data["anomalias"] = anomalias

        if options["json"]:
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
            return

        self.stdout.write("=== Relatório 2FA ===")
        for k, v in data.items():
            if k == "lockouts_ativos":
                self.stdout.write(f"{k}: {len(v)}")
            elif k == "anomalias":
                self.stdout.write(f"anomalias: {len(v)}")
            else:
                self.stdout.write(f"{k}: {v}")
        if data.get("lockouts_ativos"):
            self.stdout.write("\nLockouts:")
            for item in data["lockouts_ativos"]:
                self.stdout.write(f" - {item['username']} até {item['locked_until']}")
        if options["detailed"] and data.get("anomalias"):
            self.stdout.write("\nAnomalias:")
            for a in data["anomalias"]:
                self.stdout.write(f" - {a['username']}: {a['issue']}")

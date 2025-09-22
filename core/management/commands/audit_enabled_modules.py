import json

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Tenant

CANONICAL_KEY = "modules"


class Command(BaseCommand):
    help = 'Audita e (opcionalmente) normaliza o campo enabled_modules de todos os tenants para o formato canonical {"modules": [..]} sem quebrar dados.'

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Aplica correções (normalização) persistindo no banco."
        )
        parser.add_argument("--json", action="store_true", help="Saída em JSON (lista de objetos).")
        parser.add_argument(
            "--fail-on-dirty",
            action="store_true",
            help="Retorna código de saída !=0 se encontrar divergências (CI enforcement).",
        )

    def handle(self, *args, **opts):
        apply = opts.get("apply")
        json_out = opts.get("json")
        fail_on_dirty = opts.get("fail_on_dirty")

        report = []
        dirty_count = 0
        total = 0
        for t in Tenant.objects.all():
            total += 1
            raw = t.enabled_modules
            normalized, reason = self._normalize_preview(raw)
            is_canonical = (raw == normalized) and isinstance(raw, dict) and CANONICAL_KEY in raw
            if not is_canonical:
                dirty_count += 1
            entry = {
                "tenant_id": t.id,
                "name": t.name,
                "raw": raw,
                "normalized": normalized,
                "canonical": is_canonical,
                "reason": reason,
            }
            report.append(entry)
        if apply and dirty_count:
            with transaction.atomic():
                for r in report:
                    if not r["canonical"]:
                        Tenant.objects.filter(id=r["tenant_id"]).update(enabled_modules=r["normalized"])
        if json_out:
            self.stdout.write(
                json.dumps(
                    {"total": total, "dirty": dirty_count, "applied": apply, "items": report},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            self.stdout.write(f"Total tenants: {total} | Divergentes: {dirty_count} | Apply: {apply}")
            for r in report:
                if not r["canonical"]:
                    self.stdout.write(
                        f"[DIRTY] id={r['tenant_id']} name={r['name']} -> {r['raw']} => {r['normalized']} ({r['reason']})"
                    )
            if dirty_count == 0:
                self.stdout.write(self.style.SUCCESS("Todos os tenants já estão no formato canonical."))
            elif apply:
                self.stdout.write(self.style.SUCCESS(f"Normalização aplicada para {dirty_count} tenants."))
        if fail_on_dirty and dirty_count:
            # Código de saída não-zero para pipelines
            raise SystemExit(2)

    # --- Helpers ---
    def _normalize_preview(self, raw):
        """Retorna (normalized_dict, reason_text). NÃO salva."""
        try:
            from core.models import Tenant as _T  # evitar referência circular

            normalized_obj = _T._normalize_enabled_modules(raw)  # type: ignore
            if not isinstance(normalized_obj, dict) or CANONICAL_KEY not in normalized_obj:
                normalized_obj = {CANONICAL_KEY: []}
            if raw == normalized_obj:
                return normalized_obj, "already_canonical"
            return normalized_obj, "normalized"
        except Exception as e:
            return {CANONICAL_KEY: []}, f"error:{e.__class__.__name__}"

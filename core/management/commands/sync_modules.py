from django.core.management.base import BaseCommand

from core.models import Tenant


class Command(BaseCommand):
    help = "Verifica e corrige (opcional) o formato canonical de enabled_modules para todos os tenants."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica correções salvando alterações.")

    def handle(self, *args, **options):
        apply = options.get("apply")
        fixed = 0
        inspected = 0
        for tenant in Tenant.objects.all():
            inspected += 1
            mods = tenant.enabled_modules or {}
            canonical = None
            # Formato esperado: {"modules": [..]}
            if isinstance(mods, dict) and "modules" in mods and isinstance(mods["modules"], list):
                # já canonical
                continue
            # Legado: dict simples {mod: {...}} ou lista
            if isinstance(mods, list):
                canonical = {"modules": mods}
            elif isinstance(mods, dict):
                collected = []
                for k, v in mods.items():
                    if k == "modules":
                        continue
                    if isinstance(v, dict):
                        if v.get("enabled") is True:
                            collected.append(k)
                    elif v in (True, "enabled", 1):
                        collected.append(k)
                canonical = {"modules": collected}
            else:
                canonical = {"modules": []}
            self.stdout.write(f"Tenant {tenant.id} -> canonicalizado: {mods} => {canonical}")
            if apply:
                tenant.enabled_modules = canonical
                tenant.save(update_fields=["enabled_modules"])
                fixed += 1
        self.stdout.write(self.style.SUCCESS(f"Inspecionados={inspected} corrigidos={fixed}"))

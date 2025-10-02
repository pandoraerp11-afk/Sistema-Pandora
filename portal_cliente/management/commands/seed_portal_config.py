"""Command para criar PortalClienteConfiguracao default para tenants sem entrada.

Uso:
    python manage.py seed_portal_config [--force]

Sem --force cria apenas ausentes. Com --force atualiza valores para defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - somente para type checking
    import argparse

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Tenant
from portal_cliente.models import PortalClienteConfiguracao

DEFAULTS = {
    "checkin_antecedencia_min": 30,
    "checkin_tolerancia_pos_min": 60,
    "finalizacao_tolerancia_horas": 6,
    "cancelamento_limite_horas": 24,
    "throttle_checkin": 12,
    "throttle_finalizar": 10,
    "throttle_avaliar": 10,
}


class Command(BaseCommand):
    """Seed de configurações padrão do Portal Cliente por tenant.

    - Sem argumentos: cria somente configurações ausentes.
    - Com ``--force``: atualiza também existentes para os defaults.
    """

    help = "Cria/atualiza PortalClienteConfiguracao para todos os tenants"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:  # pragma: no cover
        """Define argumentos da linha de comando."""
        parser.add_argument("--force", action="store_true", help="Força update dos existentes com defaults")

    @transaction.atomic
    def handle(self, **options: object) -> None:  # pragma: no cover
        """Executa o seed iterando todos os tenants."""
        force: bool = bool(options.get("force"))
        created = 0
        updated = 0
        total = Tenant.objects.count()
        for tenant in Tenant.objects.all():
            cfg, was_created = PortalClienteConfiguracao.objects.get_or_create(
                tenant=tenant,
                defaults=DEFAULTS,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Criada config tenant={tenant.id}"))
            elif force:
                for k, v in DEFAULTS.items():
                    setattr(cfg, k, v)
                cfg.save(update_fields=list(DEFAULTS.keys()))
                updated += 1
                self.stdout.write(self.style.WARNING(f"Atualizada (force) tenant={tenant.id}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído: criadas={created}, atualizadas={updated}, tenants={total}",
            ),
        )

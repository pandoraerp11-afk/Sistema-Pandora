"""Comando utilitário para limpeza de cache e consolidação de tenants.

Objetivos:
 1. Limpar caches (cache default, chaves de rate limit, permission resolver, etc.).
 2. Manter apenas os tenants reais informados (por código interno) e arquivar ou excluir os demais.

Uso básico (dry-run por padrão):
  python manage.py cleanup_tenants --keep-codes 01 02

Aplicar de fato (alterar banco):
  python manage.py cleanup_tenants --keep-codes 01 02 --apply

Excluir definitivamente (ao invés de apenas inativar):
  python manage.py cleanup_tenants --keep-codes 01 02 --apply --hard-delete

Em produção (DEBUG=False) exige --force-production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Tenant

if TYPE_CHECKING:  # somente para tipagem
    import argparse


# Prefixos conhecidos de cache (se o backend suportar clear simples já cobre; mantidos aqui
# para casos de backends parciais onde apenas del específica seja necessária futuramente)
KNOWN_CACHE_PREFIXES: tuple[str, ...] = (
    "login_global_rate:",
    "permission_resolver_version:",  # hipotético (ex: shared.services.permission_resolver)
)


PREVIEW_LIMIT = 10  # número máximo de tenants exibidos no preview dry-run


@dataclass
class CleanupResult:
    """Resumo estruturado do processo de limpeza de tenants."""

    kept: int
    inactivated: int
    deleted: int
    missing_requested: list[str]


class Command(BaseCommand):
    """Comando principal de limpeza de tenants e cache."""

    help = "Limpa caches e mantém apenas os tenants com os códigos internos especificados."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Define os argumentos de linha de comando do utilitário."""
        parser.add_argument(
            "--keep-codes",
            nargs="+",
            required=True,
            help="Lista de códigos internos de tenants que devem permanecer (ex: 01 02)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Efetiva as alterações (sem esta flag é somente dry-run)",
        )
        parser.add_argument(
            "--hard-delete",
            action="store_true",
            help="Excluir definitivamente tenants não mantidos (padrão é apenas inativar)",
        )
        parser.add_argument(
            "--force-production",
            action="store_true",
            help="Permite execução quando DEBUG=False (uso consciente em produção)",
        )
        parser.add_argument(
            "--clear-sessions",
            action="store_true",
            help="Também apaga sessões (pode desconectar todos os usuários).",
        )

    def handle(self, *_args: str, **options: object) -> None:
        """Executa o fluxo principal do comando."""
        raw_keep_codes = options.get("keep_codes")
        if isinstance(raw_keep_codes, (list, tuple)) and all(isinstance(c, str) for c in raw_keep_codes):
            keep_codes = list(raw_keep_codes)
        else:  # defesa adicional (argparse sempre entrega lista pelo nargs)
            msg = "--keep-codes deve ser uma lista de strings (ex: --keep-codes 01 02)"
            raise CommandError(msg)
        apply_changes = bool(options.get("apply"))
        hard_delete = bool(options.get("hard_delete"))
        force_prod = bool(options.get("force_production"))
        clear_sessions = bool(options.get("clear_sessions"))

        if not settings.DEBUG and not force_prod:
            msg = "Ambiente com DEBUG=False detectado. Use --force-production conscientemente para prosseguir."
            raise CommandError(msg)

        if len(set(keep_codes)) != len(keep_codes):
            msg = "Existem códigos repetidos em --keep-codes."
            raise CommandError(msg)

        self.stdout.write(self.style.NOTICE("==> Iniciando limpeza de cache e consolidação de tenants"))
        self.stdout.write(f"Códigos a manter: {', '.join(keep_codes)}")
        self._clear_caches()
        if clear_sessions:
            self._clear_sessions(apply_changes=apply_changes)
        result = self._process_tenants(
            keep_codes=keep_codes,
            apply_changes=apply_changes,
            hard_delete=hard_delete,
        )

        mode = "APLICADO" if apply_changes else "DRY-RUN"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"[Resumo {mode}]"))
        self.stdout.write(f"Tenants mantidos: {result.kept}")
        if hard_delete:
            self.stdout.write(f"Tenants deletados: {result.deleted}")
        else:
            self.stdout.write(f"Tenants inativados: {result.inactivated}")
        if result.missing_requested:
            self.stdout.write(
                self.style.WARNING(f"Códigos não encontrados: {', '.join(result.missing_requested)}"),
            )
        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma alteração persistida (modo dry-run). Use --apply para efetivar.",
                ),
            )

    # ----------------- Internals -----------------
    def _clear_caches(self) -> None:
        """Limpa caches conhecidos (clear() cobre cenários padrão)."""
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("Cache principal limpo (cache.clear())."))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"Falha ao limpar cache principal: {exc}"))

    def _clear_sessions(self, *, apply_changes: bool) -> None:
        """Limpa todas as sessões persistidas se apply_changes=True."""
        total = Session.objects.count()
        if not apply_changes:
            self.stdout.write(f"Sessões a remover (dry-run): {total}")
            return
        deleted, _ = Session.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Sessões removidas: {deleted}"))

    def _process_tenants(
        self,
        *,
        keep_codes: list[str],
        apply_changes: bool,
        hard_delete: bool,
    ) -> CleanupResult:
        """Processa tenants a manter/inativar/deletar de acordo com parâmetros."""
        keep_set = {c.strip() for c in keep_codes}
        existing_qs = Tenant.objects.all().only("id", "codigo_interno", "status", "name")
        codes_existing = {t.codigo_interno for t in existing_qs if t.codigo_interno}
        missing = sorted([c for c in keep_set if c not in codes_existing])

        to_keep = [t for t in existing_qs if t.codigo_interno in keep_set]
        to_change = [t for t in existing_qs if t.codigo_interno not in keep_set]

        self.stdout.write(
            f"Total tenants: {existing_qs.count()} | Manter: {len(to_keep)} | Alterar: {len(to_change)}",
        )

        if not apply_changes:
            action = "DELETAR" if hard_delete else "INATIVAR"
            preview = to_change[:PREVIEW_LIMIT]
            for t in preview:
                self.stdout.write(f" - {action}: {t.id} {t.codigo_interno or '-'} {t.name}")
            remaining = len(to_change) - len(preview)
            if remaining > 0:
                self.stdout.write(f"   ... (+{remaining} restantes)")
            return CleanupResult(
                kept=len(to_keep),
                inactivated=len(to_change),
                deleted=0,
                missing_requested=missing,
            )

        with transaction.atomic():
            if hard_delete:
                ids = [t.id for t in to_change]
                deleted_count, _ = Tenant.objects.filter(id__in=ids).delete()
                return CleanupResult(
                    kept=len(to_keep),
                    inactivated=0,
                    deleted=deleted_count,
                    missing_requested=missing,
                )
            updated = Tenant.objects.filter(id__in=[t.id for t in to_change]).update(status="inactive")
            return CleanupResult(
                kept=len(to_keep),
                inactivated=updated,
                deleted=0,
                missing_requested=missing,
            )

"""Comando de auditoria completa de código.

Notas de manutenção (modernização incremental):
 - Evitar refatorações estruturais que alterem regras de negócio.
 - Somente ajustes de estilo/segurança/observabilidade de baixo risco.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # imports somente para tipagem
    import argparse
    from collections.abc import Iterator

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.analyzers.performance import PerformanceAnalyzer
from ai_auditor.analyzers.security import SecurityAnalyzer
from ai_auditor.analyzers.test_coverage import TestCoverageAnalyzer
from ai_auditor.models import AuditSession, CodeIssue
from core.models import CustomUser, Tenant


class Command(BaseCommand):
    """Executa uma auditoria completa do código-fonte do sistema."""

    help = "Executa uma auditoria completa do código-fonte do sistema."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Adiciona argumentos de linha de comando ao parser."""
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para executar a auditoria.")
        parser.add_argument("--user_id", type=int, help="ID do Usuário que está executando a auditoria.")

    # Helpers de redução de complexidade
    def _get_tenant(self, tenant_id: int) -> Tenant:
        try:
            return Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as e:
            msg = f"Tenant com ID {tenant_id} não encontrado."
            raise CommandError(msg) from e

    def _get_user(self, user_id: int | None) -> CustomUser | None:
        if not user_id:
            return None
        try:
            return CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f"Usuário com ID {user_id} não encontrado. Auditoria será registrada sem usuário.",
                ),
            )
            return None

    def _list_apps(self) -> list[str]:
        excluded = getattr(settings, "AI_AGENT_EXCLUDED_APPS", ["core", "admin"])
        return [
            cfg.name
            for cfg in apps.get_app_configs()
            if not cfg.name.startswith("django.") and cfg.name not in excluded
        ]

    def _iter_python_files(self, app_name: str) -> Iterator[Path]:
        app_dir = apps.get_app_config(app_name).path
        for root, _dirs, files in os.walk(app_dir):
            for fn in files:
                if fn.endswith(".py"):
                    yield Path(root) / fn

    def _analyze_file(
        self,
        analyzers: list,
        session: AuditSession,
        app_name: str,
        file_path: Path,
        counters: dict,
    ) -> None:
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:  # narrow except
            self.stdout.write(self.style.ERROR(f"Erro ao ler {file_path}: {e}"))
            return
        for analyzer in analyzers:
            try:
                issues = analyzer.analyze(str(file_path), content)
            except Exception as e:  # noqa: BLE001 - analisador externo pode falhar
                self.stdout.write(self.style.ERROR(f"Falha no analisador {analyzer.__class__.__name__}: {e}"))
                continue
            for data in issues:
                CodeIssue.objects.create(
                    session=session,
                    app_name=app_name,
                    file_path=str(file_path),
                    line_number=data.get("line_number"),
                    column_number=data.get("column_number"),
                    issue_type=data.get("issue_type"),
                    severity=data.get("severity"),
                    title=data.get("title"),
                    description=data.get("description"),
                    recommendation=data.get("recommendation"),
                    code_snippet=data.get("code_snippet"),
                    suggested_fix=data.get("suggested_fix"),
                    auto_fixable=data.get("auto_fixable", False),
                )
                counters["issues"] += 1
                sev = data.get("severity")
                if sev in counters:
                    counters[sev] += 1

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002
        """Orquestra a auditoria agregando métricas e persistindo sessão."""
        tenant_id_obj: Any = options.get("tenant_id")
        user_id_obj: Any = options.get("user_id")
        if tenant_id_obj is None:
            err = "O --tenant_id é obrigatório."
            raise CommandError(err)
        if not isinstance(tenant_id_obj, int):  # conversão defensiva
            try:
                tenant_id = int(tenant_id_obj)
            except (TypeError, ValueError) as e:
                msg = "tenant_id inválido"
                raise CommandError(msg) from e
        else:
            tenant_id = tenant_id_obj
        if user_id_obj is None:
            user_id: int | None = None
        elif isinstance(user_id_obj, int):
            user_id = user_id_obj
        else:
            try:
                user_id = int(user_id_obj)
            except (TypeError, ValueError):
                user_id = None

        tenant = self._get_tenant(tenant_id)
        user = self._get_user(user_id)

        self.stdout.write(self.style.SUCCESS(f"Iniciando auditoria completa para o Tenant: {tenant.name}"))
        session = AuditSession.objects.create(tenant=tenant, user=user, status="running")
        self.stdout.write(self.style.SUCCESS(f"Sessão de Auditoria criada: {session.id}"))

        analyzers = [
            SecurityAnalyzer(tenant, session),
            PerformanceAnalyzer(tenant, session),
            TestCoverageAnalyzer(tenant, session),
        ]
        counters = {"files": 0, "issues": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

        for app_name in self._list_apps():
            self.stdout.write(self.style.NOTICE(f"Analisando app: {app_name}"))
            for file_path in self._iter_python_files(app_name):
                counters["files"] += 1
                self._analyze_file(analyzers, session, app_name, file_path, counters)

        # Persistir agregados
        session.total_files_analyzed = counters["files"]
        session.total_issues = counters["issues"]
        session.critical_issues = counters["critical"]
        session.high_issues = counters["high"]
        session.medium_issues = counters["medium"]
        session.low_issues = counters["low"]
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save()

        self.stdout.write(self.style.SUCCESS("Auditoria completa finalizada com sucesso!"))
        self.stdout.write(self.style.SUCCESS(f"Total de arquivos analisados: {counters['files']}"))
        self.stdout.write(self.style.SUCCESS(f"Total de problemas encontrados: {counters['issues']}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Críticos: {counters['critical']}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Altos: {counters['high']}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Médios: {counters['medium']}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Baixos: {counters['low']}"))

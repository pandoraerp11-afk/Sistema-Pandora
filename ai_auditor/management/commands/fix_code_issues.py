"""Comando para aplicar correções automáticas em problemas de código.

Escopo: ajustes mínimos para remover alertas de lint sem alterar regras de negócio.
Refatorações de complexidade (C901/PLR09xx) serão feitas em lote posterior.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.generators.code_fixer import CodeFixer
from ai_auditor.models import AuditSession, CodeIssue

if TYPE_CHECKING:  # imports somente para tipagem
    import argparse


class Command(BaseCommand):
    """Aplica correções automáticas para problemas de código identificados."""

    help = "Aplica correções automáticas para problemas de código identificados."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Define argumentos de CLI."""
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para aplicar as correções.")
        parser.add_argument(
            "--issue_id",
            type=int,
            nargs="?",
            default=None,
            help="ID de um problema específico para corrigir.",
        )
        parser.add_argument(
            "--session_id",
            type=int,
            nargs="?",
            default=None,
            help="ID de uma sessão de auditoria para corrigir todos os problemas auto-corrigíveis.",
        )

    def _apply_single_issue(self, issue: CodeIssue, fixer: CodeFixer, fixed_count: int) -> int:
        """Aplica correção a uma única issue (helper para reduzir complexidade)."""
        with Path(issue.file_path).open(encoding="utf-8") as f:
            original_content = f.read()
        if issue.suggested_fix and fixer.apply_fix(issue.file_path, original_content, issue.suggested_fix):
            issue.status = "fixed"
            issue.fixed_at = timezone.now()
            issue.save()
            fixed_count += 1
            self.stdout.write(self.style.SUCCESS(f"Problema {issue.id} corrigido: {issue.title}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"Não foi possível corrigir o problema {issue.id}: {issue.title}"),
            )
        return fixed_count

    def handle(self, **options: dict) -> None:
        """Executa a aplicação de correções conforme filtros informados."""
        tenant_id = options.get("tenant_id")
        issue_id = options.get("issue_id")
        session_id = options.get("session_id")

        if not tenant_id:
            _msg_required = "O --tenant_id é obrigatório."
            raise CommandError(_msg_required)

        try:
            tenant = apps.get_model("core", "Tenant").objects.get(id=tenant_id)
        except apps.get_model("core", "Tenant").DoesNotExist as e:
            _tenant_nf = f"Tenant com ID {tenant_id} não encontrado."
            raise CommandError(_tenant_nf) from e

        if not issue_id and not session_id:
            _msg_choice = "Você deve fornecer --issue_id ou --session_id."
            raise CommandError(_msg_choice)

        fixer = CodeFixer(tenant, None)  # Sessão será atribuída depois se necessário
        fixed_count = 0

        if issue_id:
            try:
                issue = CodeIssue.objects.get(id=issue_id, session__tenant=tenant, auto_fixable=True)
            except CodeIssue.DoesNotExist as e:
                _issue_nf = (
                    f"Problema com ID {issue_id} não encontrado ou não é auto-corrigível para o Tenant {tenant.name}."
                )
                raise CommandError(_issue_nf) from e
            fixed_count = self._apply_single_issue(issue, fixer, fixed_count)
            return
        if session_id:
            try:
                session = AuditSession.objects.get(id=session_id, tenant=tenant)
                self.stdout.write(
                    self.style.NOTICE(
                        f"Tentando corrigir problemas auto-corrigíveis da sessão: {session.id}",
                    ),
                )

                issues_to_fix = CodeIssue.objects.filter(session=session, auto_fixable=True, status="open")

                for issue in issues_to_fix:
                    try:
                        fixed_count = self._apply_single_issue(issue, fixer, fixed_count)
                    except Exception as e:  # noqa: BLE001
                        self.stdout.write(self.style.ERROR(f"Erro ao corrigir problema {issue.id}: {e}"))

                session.fixes_applied = fixed_count
                session.save()

            except AuditSession.DoesNotExist as e:
                _session_nf = f"Sessão de Auditoria com ID {session_id} não encontrada para o Tenant {tenant.name}."
                raise CommandError(_session_nf) from e

        self.stdout.write(
            self.style.SUCCESS(
                f"Processo de correção finalizado. Total de problemas corrigidos: {fixed_count}",
            ),
        )

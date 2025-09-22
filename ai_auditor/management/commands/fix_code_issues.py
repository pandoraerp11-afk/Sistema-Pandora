from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.generators.code_fixer import CodeFixer
from ai_auditor.models import AuditSession, CodeIssue


class Command(BaseCommand):
    help = "Aplica correções automáticas para problemas de código identificados."

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para aplicar as correções.")
        parser.add_argument(
            "--issue_id", type=int, nargs="?", default=None, help="ID de um problema específico para corrigir."
        )
        parser.add_argument(
            "--session_id",
            type=int,
            nargs="?",
            default=None,
            help="ID de uma sessão de auditoria para corrigir todos os problemas auto-corrigíveis.",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        issue_id = options.get("issue_id")
        session_id = options.get("session_id")

        if not tenant_id:
            raise CommandError("O --tenant_id é obrigatório.")

        try:
            tenant = apps.get_model("core", "Tenant").objects.get(id=tenant_id)
        except apps.get_model("core", "Tenant").DoesNotExist:
            raise CommandError(f"Tenant com ID {tenant_id} não encontrado.")

        if not issue_id and not session_id:
            raise CommandError("Você deve fornecer --issue_id ou --session_id.")

        fixer = CodeFixer(tenant, None)  # Session will be updated if needed
        fixed_count = 0

        if issue_id:
            try:
                issue = CodeIssue.objects.get(id=issue_id, session__tenant=tenant, auto_fixable=True)
                self.stdout.write(self.style.NOTICE(f"Tentando corrigir problema: {issue.title} ({issue.file_path})"))

                # Read the file content
                with open(issue.file_path, encoding="utf-8") as f:
                    original_content = f.read()

                # Apply the fix
                if fixer.apply_fix(issue.file_path, original_content, issue.suggested_fix):
                    issue.status = "fixed"
                    issue.fixed_at = timezone.now()
                    issue.save()
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Problema {issue.id} corrigido com sucesso."))
                else:
                    self.stdout.write(self.style.WARNING(f"Não foi possível corrigir o problema {issue.id}."))

            except CodeIssue.DoesNotExist:
                raise CommandError(
                    f"Problema com ID {issue_id} não encontrado ou não é auto-corrigível para o Tenant {tenant.name}."
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao corrigir problema {issue_id}: {e}"))

        elif session_id:
            try:
                session = AuditSession.objects.get(id=session_id, tenant=tenant)
                self.stdout.write(
                    self.style.NOTICE(f"Tentando corrigir problemas auto-corrigíveis da sessão: {session.id}")
                )

                issues_to_fix = CodeIssue.objects.filter(session=session, auto_fixable=True, status="open")

                for issue in issues_to_fix:
                    try:
                        with open(issue.file_path, encoding="utf-8") as f:
                            original_content = f.read()

                        if fixer.apply_fix(issue.file_path, original_content, issue.suggested_fix):
                            issue.status = "fixed"
                            issue.fixed_at = timezone.now()
                            issue.save()
                            fixed_count += 1
                            self.stdout.write(self.style.SUCCESS(f"Problema {issue.id} corrigido: {issue.title}"))
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"Não foi possível corrigir o problema {issue.id}: {issue.title}")
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Erro ao corrigir problema {issue.id} ({issue.title}): {e}")
                        )

                session.fixes_applied = fixed_count
                session.save()

            except AuditSession.DoesNotExist:
                raise CommandError(
                    f"Sessão de Auditoria com ID {session_id} não encontrada para o Tenant {tenant.name}."
                )

        self.stdout.write(
            self.style.SUCCESS(f"Processo de correção finalizado. Total de problemas corrigidos: {fixed_count}")
        )

import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.analyzers.performance import PerformanceAnalyzer
from ai_auditor.analyzers.security import SecurityAnalyzer
from ai_auditor.analyzers.test_coverage import TestCoverageAnalyzer
from ai_auditor.models import AuditSession, CodeIssue


class Command(BaseCommand):
    help = "Executa uma auditoria completa do código-fonte do sistema."

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para executar a auditoria.")
        parser.add_argument("--user_id", type=int, help="ID do Usuário que está executando a auditoria.")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        user_id = options.get("user_id")

        if not tenant_id:
            raise CommandError("O --tenant_id é obrigatório.")

        try:
            tenant = apps.get_model("core", "Tenant").objects.get(id=tenant_id)
        except apps.get_model("core", "Tenant").DoesNotExist:
            raise CommandError(f"Tenant com ID {tenant_id} não encontrado.")

        user = None
        if user_id:
            try:
                user = apps.get_model("core", "CustomUser").objects.get(id=user_id)
            except apps.get_model("core", "CustomUser").DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Usuário com ID {user_id} não encontrado. Auditoria será registrada sem usuário."
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"Iniciando auditoria completa para o Tenant: {tenant.name}"))

        session = AuditSession.objects.create(tenant=tenant, user=user, status="running")
        self.stdout.write(self.style.SUCCESS(f"Sessão de Auditoria criada: {session.id}"))

        excluded_apps = getattr(settings, "AI_AGENT_EXCLUDED_APPS", ["core", "admin"])
        all_apps = [
            app_config.name
            for app_config in apps.get_app_configs()
            if not app_config.name.startswith("django.") and app_config.name not in excluded_apps
        ]

        total_files_analyzed = 0
        total_issues_found = 0
        critical_issues = 0
        high_issues = 0
        medium_issues = 0
        low_issues = 0

        analyzers = [
            SecurityAnalyzer(tenant, session),
            PerformanceAnalyzer(tenant, session),
            TestCoverageAnalyzer(tenant, session),
        ]

        for app_name in all_apps:
            self.stdout.write(self.style.NOTICE(f"Analisando app: {app_name}"))
            app_dir = apps.get_app_config(app_name).path

            for root, _, files in os.walk(app_dir):
                for file_name in files:
                    if file_name.endswith(".py"):
                        file_path = os.path.join(root, file_name)
                        total_files_analyzed += 1
                        try:
                            with open(file_path, encoding="utf-8") as f:
                                content = f.read()

                            for analyzer in analyzers:
                                found_issues = analyzer.analyze(file_path, content)
                                for issue_data in found_issues:
                                    CodeIssue.objects.create(
                                        session=session,
                                        app_name=app_name,
                                        file_path=file_path,
                                        line_number=issue_data.get("line_number"),
                                        column_number=issue_data.get("column_number"),
                                        issue_type=issue_data.get("issue_type"),
                                        severity=issue_data.get("severity"),
                                        title=issue_data.get("title"),
                                        description=issue_data.get("description"),
                                        recommendation=issue_data.get("recommendation"),
                                        code_snippet=issue_data.get("code_snippet"),
                                        suggested_fix=issue_data.get("suggested_fix"),
                                        auto_fixable=issue_data.get("auto_fixable", False),
                                    )
                                    total_issues_found += 1
                                    if issue_data.get("severity") == "critical":
                                        critical_issues += 1
                                    elif issue_data.get("severity") == "high":
                                        high_issues += 1
                                    elif issue_data.get("severity") == "medium":
                                        medium_issues += 1
                                    elif issue_data.get("severity") == "low":
                                        low_issues += 1

                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Erro ao analisar {file_path}: {e}"))

        session.total_files_analyzed = total_files_analyzed
        session.total_issues = total_issues_found
        session.critical_issues = critical_issues
        session.high_issues = high_issues
        session.medium_issues = medium_issues
        session.low_issues = low_issues
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save()

        self.stdout.write(self.style.SUCCESS("Auditoria completa finalizada com sucesso!"))
        self.stdout.write(self.style.SUCCESS(f"Total de arquivos analisados: {total_files_analyzed}"))
        self.stdout.write(self.style.SUCCESS(f"Total de problemas encontrados: {total_issues_found}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Críticos: {critical_issues}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Altos: {high_issues}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Médios: {medium_issues}"))
        self.stdout.write(self.style.SUCCESS(f"Problemas Baixos: {low_issues}"))

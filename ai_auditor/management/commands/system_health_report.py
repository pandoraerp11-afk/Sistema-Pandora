import os

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.models import AuditSession, CodeIssue
from ai_auditor.reports.exporters import ReportExporter


class Command(BaseCommand):
    help = "Gera um relatório de saúde do sistema com base nas últimas auditorias."

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para gerar o relatório.")
        parser.add_argument(
            "--format",
            type=str,
            default="pdf",
            choices=["pdf", "excel", "csv"],
            help="Formato do relatório (pdf, excel, csv).",
        )
        parser.add_argument("--output_dir", type=str, default="./reports", help="Diretório de saída para o relatório.")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        report_format = options.get("format")
        output_dir = options.get("output_dir")

        if not tenant_id:
            raise CommandError("O --tenant_id é obrigatório.")

        try:
            tenant = apps.get_model("core", "Tenant").objects.get(id=tenant_id)
        except apps.get_model("core", "Tenant").DoesNotExist:
            raise CommandError(f"Tenant com ID {tenant_id} não encontrado.")

        os.makedirs(output_dir, exist_ok=True)

        self.stdout.write(self.style.SUCCESS(f"Gerando relatório de saúde do sistema para o Tenant: {tenant.name}"))

        latest_session = AuditSession.objects.filter(tenant=tenant).order_by("-started_at").first()

        if not latest_session:
            self.stdout.write(
                self.style.WARNING("Nenhuma sessão de auditoria encontrada para este Tenant. Gerando relatório vazio.")
            )
            issues = CodeIssue.objects.none()
        else:
            issues = CodeIssue.objects.filter(session=latest_session)

        exporter = ReportExporter()
        report_file_name = (
            f"system_health_report_{tenant.name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{report_format}"
        )
        report_path = os.path.join(output_dir, report_file_name)

        if report_format == "pdf":
            exporter.export_to_pdf(issues, report_path)
        elif report_format == "excel":
            exporter.export_to_excel(issues, report_path)
        elif report_format == "csv":
            exporter.export_to_csv(issues, report_path)
        else:
            raise CommandError(f"Formato de relatório inválido: {report_format}")

        self.stdout.write(self.style.SUCCESS(f"Relatório gerado com sucesso em: {report_path}"))

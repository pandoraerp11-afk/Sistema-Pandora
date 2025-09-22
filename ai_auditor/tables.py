import django_tables2 as tables

from .models import AuditSession, CodeIssue, GeneratedTest


class AuditSessionTable(tables.Table):
    id = tables.Column(linkify=True)
    total_issues = tables.Column(verbose_name="Problemas")
    critical_issues = tables.Column(verbose_name="Críticos")
    high_issues = tables.Column(verbose_name="Altos")
    medium_issues = tables.Column(verbose_name="Médios")
    low_issues = tables.Column(verbose_name="Baixos")

    class Meta:
        model = AuditSession
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "id",
            "tenant",
            "user",
            "status",
            "started_at",
            "completed_at",
            "total_issues",
            "critical_issues",
            "high_issues",
            "medium_issues",
            "low_issues",
        )


class CodeIssueTable(tables.Table):
    id = tables.Column(linkify=True)
    file_path = tables.Column(verbose_name="Arquivo")
    issue_type = tables.Column(verbose_name="Tipo")
    severity = tables.Column(verbose_name="Severidade")
    status = tables.Column(verbose_name="Status")
    title = tables.Column(verbose_name="Título")

    class Meta:
        model = CodeIssue
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "id",
            "session",
            "app_name",
            "file_path",
            "line_number",
            "issue_type",
            "severity",
            "status",
            "title",
            "auto_fixable",
        )


class GeneratedTestTable(tables.Table):
    id = tables.Column(linkify=True)
    app_name = tables.Column(verbose_name="App")
    model_name = tables.Column(verbose_name="Modelo")
    test_type = tables.Column(verbose_name="Tipo de Teste")
    test_file_path = tables.Column(verbose_name="Caminho do Arquivo")
    is_applied = tables.Column(verbose_name="Aplicado")

    class Meta:
        model = GeneratedTest
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id", "session", "app_name", "model_name", "test_type", "test_file_path", "is_applied", "applied_at")

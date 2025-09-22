from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CustomUser, Tenant, TimestampedModel


class AuditSession(TimestampedModel):
    STATUS_CHOICES = [
        ("running", _("Em Execução")),
        ("completed", _("Concluída")),
        ("failed", _("Falhou")),
        ("cancelled", _("Cancelada")),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_sessions")
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_files_analyzed = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    critical_issues = models.IntegerField(default=0)
    high_issues = models.IntegerField(default=0)
    medium_issues = models.IntegerField(default=0)
    low_issues = models.IntegerField(default=0)
    tests_generated = models.IntegerField(default=0)
    fixes_applied = models.IntegerField(default=0)
    analysis_config = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("Sessão de Auditoria")
        verbose_name_plural = _("Sessões de Auditoria")
        ordering = ["-started_at"]


class CodeIssue(TimestampedModel):
    ISSUE_TYPES = [
        ("security", _("Segurança")),
        ("performance", _("Performance")),
        ("quality", _("Qualidade")),
        ("documentation", _("Documentação")),
        ("testing", _("Testes")),
        ("style", _("Estilo")),
        ("complexity", _("Complexidade")),
        ("duplication", _("Duplicação")),
    ]

    SEVERITY_CHOICES = [
        ("critical", _("Crítico")),
        ("high", _("Alto")),
        ("medium", _("Médio")),
        ("low", _("Baixo")),
    ]

    STATUS_CHOICES = [
        ("open", _("Aberto")),
        ("in_progress", _("Em Andamento")),
        ("fixed", _("Corrigido")),
        ("ignored", _("Ignorado")),
        ("false_positive", _("Falso Positivo")),
    ]

    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name="issues")
    app_name = models.CharField(max_length=100)
    file_path = models.CharField(max_length=500)
    line_number = models.IntegerField(null=True, blank=True)
    column_number = models.IntegerField(null=True, blank=True)
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommendation = models.TextField()
    code_snippet = models.TextField(blank=True, null=True)
    suggested_fix = models.TextField(blank=True, null=True)
    auto_fixable = models.BooleanField(default=False)
    fixed_at = models.DateTimeField(null=True, blank=True)
    fixed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = _("Problema de Código")
        verbose_name_plural = _("Problemas de Código")
        ordering = ["-severity", "-created_at"]


class GeneratedTest(TimestampedModel):
    TEST_TYPES = [
        ("model", _("Teste de Model")),
        ("view", _("Teste de View")),
        ("form", _("Teste de Form")),
        ("api", _("Teste de API")),
        ("integration", _("Teste de Integração")),
    ]

    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name="generated_tests")
    app_name = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    test_type = models.CharField(max_length=20, choices=TEST_TYPES)
    test_file_path = models.CharField(max_length=500)
    test_code = models.TextField()
    is_applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Teste Gerado")
        verbose_name_plural = _("Testes Gerados")


class AIAuditorSettings(TimestampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="ai_auditor_settings")
    auto_fix_enabled = models.BooleanField(default=False)
    auto_test_generation = models.BooleanField(default=True)
    excluded_apps = models.JSONField(default=list, blank=True)
    analysis_schedule = models.CharField(max_length=100, blank=True, null=True)  # Cron format
    email_notifications = models.BooleanField(default=True)
    critical_threshold = models.IntegerField(default=10)

    class Meta:
        verbose_name = _("Configurações do Agente IA")
        verbose_name_plural = _("Configurações do Agente IA")

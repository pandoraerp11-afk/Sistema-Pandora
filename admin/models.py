# admin/models.py (Versão Corrigida)

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Tenant, TimestampedModel


class TenantMetrics(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="metrics", verbose_name="Empresa")
    date = models.DateField(verbose_name="Data da Métrica")
    active_users = models.PositiveIntegerField(default=0, verbose_name="Usuários Ativos")
    total_users = models.PositiveIntegerField(default=0, verbose_name="Total de Usuários")
    storage_used = models.BigIntegerField(default=0, help_text="Em bytes", verbose_name="Armazenamento Utilizado")
    api_requests = models.PositiveIntegerField(default=0, verbose_name="Requisições de API")
    response_time_avg = models.FloatField(
        default=0.0, help_text="Em milissegundos", verbose_name="Tempo de Resposta Médio"
    )
    error_rate = models.FloatField(default=0.0, help_text="Percentual de erros", verbose_name="Taxa de Erros")
    uptime = models.FloatField(default=100.0, help_text="Percentual de uptime", verbose_name="Uptime")

    class Meta:
        unique_together = ("tenant", "date")
        ordering = ["-date", "tenant"]
        verbose_name = "Métrica da Empresa"
        verbose_name_plural = "Métricas das Empresas"

    def __str__(self):
        return f"{self.tenant.name} - {self.date}"


class SystemAlert(TimestampedModel):
    SEVERITY_CHOICES = [("low", "Baixa"), ("medium", "Média"), ("high", "Alta"), ("critical", "Crítica")]
    STATUS_CHOICES = [("open", "Aberto"), ("acknowledged", "Reconhecido"), ("resolved", "Resolvido")]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    alert_type = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=100, default="system")
    metadata = models.JSONField(default=dict, blank=True)
    # Campos de auditoria / responsáveis
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts_assigned"
    )  # legado
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts_acknowledged"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts_resolved"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alerta do Sistema"
        verbose_name_plural = "Alertas do Sistema"

    def __str__(self):
        # Ajuste para testes: inclui severidade em caixa alta entre colchetes
        return f"[{self.severity.upper()}] {self.title}" if self.severity else self.title

    def acknowledge(self, user):
        self.status = "acknowledged"
        self.assigned_to = user  # manter compatibilidade
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["status", "assigned_to", "acknowledged_by", "acknowledged_at", "updated_at"])

    def resolve(self, user=None, notes: str = ""):
        self.status = "resolved"
        if user:
            self.resolved_by = user
        if notes:
            self.resolution_notes = notes
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_by", "resolution_notes", "resolved_at", "updated_at"])


class TenantConfiguration(TimestampedModel):
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="configuration", verbose_name="Empresa"
    )
    max_users = models.PositiveIntegerField(default=100, verbose_name="Máximo de Usuários")
    max_storage_mb = models.PositiveIntegerField(default=1024, verbose_name="Máximo de Armazenamento (MB)")
    max_api_requests_per_hour = models.PositiveIntegerField(default=1000, verbose_name="Máx. Requisições de API/hora")
    require_2fa = models.BooleanField(default=False, verbose_name="Exigir Autenticação de 2 Fatores")
    backup_enabled = models.BooleanField(default=True, verbose_name="Backup Habilitado")
    custom_branding = models.JSONField(default=dict, blank=True, verbose_name="Customização de Marca")

    class Meta:
        verbose_name = "Configuração da Empresa"
        verbose_name_plural = "Configurações das Empresas"

    def __str__(self):
        return f"Configuração - {self.tenant.name}"


class AdminActivity(TimestampedModel):
    ACTION_CHOICES = [
        ("create", "Criar"),
        ("update", "Atualizar"),
        ("delete", "Excluir"),
        ("view", "Visualizar"),
        ("backup", "Backup"),
        ("restore", "Restaurar"),
    ]
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Usuário Admin"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Ação")
    resource_type = models.CharField(max_length=50, verbose_name="Tipo de Recurso")
    resource_id = models.CharField(max_length=100, blank=True, verbose_name="ID do Recurso")
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empresa Afetada")
    description = models.TextField(verbose_name="Descrição da Atividade")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Endereço IP")
    before_data = models.JSONField(default=dict, blank=True, verbose_name="Dados (Antes)")
    after_data = models.JSONField(default=dict, blank=True, verbose_name="Dados (Depois)")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Atividade Administrativa"
        verbose_name_plural = "Atividades Administrativas"

    def __str__(self):
        return f"{self.admin_user or 'Sistema'} - {self.action} em {self.resource_type}"


class TenantBackup(TimestampedModel):
    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("running", "Executando"),
        ("completed", "Concluído"),
        ("failed", "Falhou"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="backups", verbose_name="Empresa")
    backup_type = models.CharField(max_length=20, default="full", verbose_name="Tipo de Backup")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Status")
    file_path = models.CharField(max_length=500, blank=True, verbose_name="Caminho do Arquivo")
    file_size = models.BigIntegerField(default=0, help_text="Em bytes", verbose_name="Tamanho do Arquivo")
    checksum = models.CharField(max_length=64, blank=True, verbose_name="Checksum")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Iniciado em")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")
    error_message = models.TextField(blank=True, verbose_name="Mensagem de Erro")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Backup da Empresa"
        verbose_name_plural = "Backups das Empresas"

    def __str__(self):
        return f"Backup {self.tenant.name} - {self.created_at.strftime('%Y-%m-%d')}"

    @property  # CORREÇÃO: Propriedade 'duration' re-adicionada
    def duration(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class SystemConfiguration(TimestampedModel):
    key = models.CharField(max_length=100, unique=True, verbose_name="Chave")
    value = models.JSONField(verbose_name="Valor")
    description = models.TextField(blank=True, verbose_name="Descrição")
    category = models.CharField(max_length=50, default="general", verbose_name="Categoria")
    is_public = models.BooleanField(default=False)  # CORREÇÃO: Campo 'is_public' re-adicionado
    is_editable = models.BooleanField(default=True, verbose_name="Editável")

    class Meta:
        ordering = ["category", "key"]
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return self.key


class TenantUsageReport(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="usage_reports", verbose_name="Empresa")
    report_type = models.CharField(max_length=50, verbose_name="Tipo de Relatório")
    period_start = models.DateTimeField(verbose_name="Início do Período")
    period_end = models.DateTimeField(verbose_name="Fim do Período")
    report_data = models.JSONField(default=dict, verbose_name="Dados do Relatório")
    summary = models.JSONField(default=dict, verbose_name="Resumo")
    file_path = models.CharField(max_length=500, blank=True, verbose_name="Caminho do Arquivo")
    file_format = models.CharField(max_length=10, default="json", verbose_name="Formato")
    is_generated = models.BooleanField(default=False, verbose_name="Gerado?")
    generated_at = models.DateTimeField(null=True, blank=True, verbose_name="Gerado em")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Relatório de Uso"
        verbose_name_plural = "Relatórios de Uso"

    def __str__(self):
        return f"Relatório de {self.report_type} para {self.tenant.name}"

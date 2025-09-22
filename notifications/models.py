from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from core.models import Tenant, TimestampedModel

User = get_user_model()


class Notification(TimestampedModel):
    """
    Modelo principal para notificações do sistema.
    Centraliza todos os avisos internos com suporte a multitenancy.
    """

    TIPO_CHOICES = [
        ("info", "Informação"),
        ("warning", "Aviso"),
        ("error", "Erro"),
        ("success", "Sucesso"),
        ("alert", "Alerta"),
    ]

    PRIORIDADE_CHOICES = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
        ("critica", "Crítica"),
    ]

    STATUS_CHOICES = [
        ("nao_lida", "Não Lida"),
        ("lida", "Lida"),
        ("arquivada", "Arquivada"),
        ("expirada", "Expirada"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="Empresa", related_name="notificacoes")

    usuario_destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Usuário Destinatário",
        related_name="notificacoes_recebidas",
    )

    titulo = models.CharField(max_length=200, verbose_name="Título")
    mensagem = models.TextField(verbose_name="Mensagem")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="info", verbose_name="Tipo")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default="media", verbose_name="Prioridade")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="nao_lida", verbose_name="Status")

    data_expiracao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Expiração")
    data_leitura = models.DateTimeField(null=True, blank=True, verbose_name="Data de Leitura")

    # Campos para referência genérica (opcional)
    # content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    # object_id = models.PositiveIntegerField(null=True, blank=True)
    # content_object = GenericForeignKey('content_type', 'object_id')

    # URL de ação (para redirecionamento)
    # assume_scheme='https' será aplicado em formulários; em modelos Django 5 não existe argumento,
    # ajuste será feito via ModelForm se necessário. Campo mantido simples.
    url_acao = models.URLField(null=True, blank=True, verbose_name="URL de Ação")

    # Metadados para integração
    modulo_origem = models.CharField(max_length=50, null=True, blank=True, verbose_name="Módulo de Origem")
    evento_origem = models.CharField(max_length=100, null=True, blank=True, verbose_name="Evento de Origem")
    dados_extras = models.JSONField(default=dict, blank=True, verbose_name="Dados Extras")

    def marcar_como_lida(self):
        """Marca a notificação como lida."""
        self.status = "lida"
        self.data_leitura = timezone.now()
        self.save(update_fields=["status", "data_leitura"])

        # Log da ação
        LogNotificacao.objects.create(
            notificacao=self, usuario=self.usuario_destinatario, acao="Notificação marcada como lida."
        )

    def arquivar(self):
        """Arquiva a notificação."""
        self.status = "arquivada"
        self.save(update_fields=["status"])

        # Log da ação
        LogNotificacao.objects.create(
            notificacao=self, usuario=self.usuario_destinatario, acao="Notificação arquivada."
        )

    def is_expirada(self):
        """Verifica se a notificação está expirada."""
        if self.data_expiracao:
            return timezone.now() > self.data_expiracao
        return False

    def expirar_se_necessario(self):
        """Expira a notificação se necessário."""
        if self.is_expirada() and self.status != "expirada":
            self.status = "expirada"
            self.save(update_fields=["status"])

            # Log da ação
            LogNotificacao.objects.create(notificacao=self, usuario=None, acao="Notificação expirada automaticamente.")

    def get_icone_tipo(self):
        """Retorna o ícone FontAwesome baseado no tipo."""
        icones = {
            "info": "fas fa-info-circle",
            "warning": "fas fa-exclamation-triangle",
            "error": "fas fa-times-circle",
            "success": "fas fa-check-circle",
            "alert": "fas fa-bell",
        }
        return icones.get(self.tipo, "fas fa-bell")

    def get_cor_prioridade(self):
        """Retorna a cor CSS baseada na prioridade."""
        cores = {
            "baixa": "secondary",
            "media": "info",
            "alta": "warning",
            "critica": "danger",
        }
        return cores.get(self.prioridade, "info")

    def __str__(self):
        return f"{self.titulo} - {self.usuario_destinatario.username}"

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "usuario_destinatario", "status"]),
            models.Index(fields=["tenant", "tipo", "prioridade"]),
            models.Index(fields=["modulo_origem", "evento_origem"]),
        ]


class LogNotificacao(models.Model):
    """
    Log de ações realizadas nas notificações.
    """

    notificacao = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="logs", verbose_name="Notificação"
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Usuário")
    acao = models.CharField(max_length=255, verbose_name="Ação")
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name="Data e Hora")

    def __str__(self):
        return (
            f"Log de {self.notificacao.titulo} por {self.usuario.username if self.usuario else 'Sistema'}: {self.acao}"
        )

    class Meta:
        verbose_name = "Log de Notificação"
        verbose_name_plural = "Logs de Notificações"
        ordering = ["-data_hora"]


class ConfiguracaoNotificacao(TimestampedModel):
    """
    Configurações de notificação por tenant.
    """

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="configuracao_notificacao", verbose_name="Empresa"
    )

    # Configurações de expiração automática
    dias_expiracao_padrao = models.PositiveIntegerField(default=30, verbose_name="Dias para Expiração Padrão")

    # Configurações de limpeza automática
    dias_retencao_lidas = models.PositiveIntegerField(
        default=90, verbose_name="Dias de Retenção para Notificações Lidas"
    )
    dias_retencao_arquivadas = models.PositiveIntegerField(
        default=365, verbose_name="Dias de Retenção para Notificações Arquivadas"
    )

    # Configurações de envio
    max_notificacoes_por_hora = models.PositiveIntegerField(default=50, verbose_name="Máximo de Notificações por Hora")

    # Configurações de agrupamento
    agrupar_notificacoes_similares = models.BooleanField(default=True, verbose_name="Agrupar Notificações Similares")

    # Configurações de canais (para futuras implementações)
    email_habilitado = models.BooleanField(default=True, verbose_name="E-mail Habilitado")
    push_habilitado = models.BooleanField(default=True, verbose_name="Push Notifications Habilitado")
    sms_habilitado = models.BooleanField(default=False, verbose_name="SMS Habilitado")

    class UpsertManager(models.Manager):
        def create(self, **kwargs):  # type: ignore
            tenant = kwargs.get("tenant")
            if tenant is None:
                return super().create(**kwargs)
            obj, created = super().get_or_create(tenant=tenant, defaults=kwargs)
            if not created:
                # Atualizar somente campos fornecidos explícitos (exceto tenant)
                dirty = False
                update_fields = []
                for k, v in kwargs.items():
                    if k == "tenant":
                        continue
                    if hasattr(obj, k) and getattr(obj, k) != v:
                        setattr(obj, k, v)
                        dirty = True
                        update_fields.append(k)
                if dirty:
                    obj.save(update_fields=update_fields)
            return obj

    objects = UpsertManager()

    def __str__(self):
        return f"Configurações de {self.tenant.name}"

    class Meta:
        verbose_name = "Configuração de Notificação"
        verbose_name_plural = "Configurações de Notificações"


class PreferenciaUsuarioNotificacao(TimestampedModel):
    """
    Preferências de notificação por usuário.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferencia_notificacao",
        verbose_name="Usuário",
    )

    # Preferências gerais
    receber_notificacoes = models.BooleanField(default=True, verbose_name="Receber Notificações")

    # Preferências por tipo
    receber_info = models.BooleanField(default=True, verbose_name="Receber Informações")
    receber_warning = models.BooleanField(default=True, verbose_name="Receber Avisos")
    receber_error = models.BooleanField(default=True, verbose_name="Receber Erros")
    receber_success = models.BooleanField(default=True, verbose_name="Receber Sucessos")
    receber_alert = models.BooleanField(default=True, verbose_name="Receber Alertas")

    # Preferências por prioridade
    receber_baixa = models.BooleanField(default=True, verbose_name="Receber Prioridade Baixa")
    receber_media = models.BooleanField(default=True, verbose_name="Receber Prioridade Média")
    receber_alta = models.BooleanField(default=True, verbose_name="Receber Prioridade Alta")
    receber_critica = models.BooleanField(default=True, verbose_name="Receber Prioridade Crítica")

    # Preferências por módulo
    modulos_bloqueados = models.JSONField(default=list, blank=True, verbose_name="Módulos Bloqueados")

    # Configurações de canais (para futuras implementações)
    email_habilitado = models.BooleanField(default=True, verbose_name="E-mail Habilitado")
    push_habilitado = models.BooleanField(default=True, verbose_name="Push Notifications Habilitado")
    sms_habilitado = models.BooleanField(default=False, verbose_name="SMS Habilitado")

    class UpsertManager(models.Manager):
        def create(self, **kwargs):  # type: ignore
            usuario = kwargs.get("usuario")
            if usuario is None:
                return super().create(**kwargs)
            obj, created = super().get_or_create(usuario=usuario, defaults=kwargs)
            if not created:
                dirty = False
                update_fields = []
                for k, v in kwargs.items():
                    if k == "usuario":
                        continue
                    if hasattr(obj, k) and getattr(obj, k) != v:
                        setattr(obj, k, v)
                        dirty = True
                        update_fields.append(k)
                if dirty:
                    obj.save(update_fields=update_fields)
            return obj

    objects = UpsertManager()

    def deve_receber_notificacao(self, tipo, prioridade, modulo_origem=None):
        """
        Verifica se o usuário deve receber uma notificação baseado em suas preferências.
        """
        if not self.receber_notificacoes:
            return False

        # Verificar tipo
        if (
            tipo == "info"
            and not self.receber_info
            or tipo == "warning"
            and not self.receber_warning
            or tipo == "error"
            and not self.receber_error
            or tipo == "success"
            and not self.receber_success
            or tipo == "alert"
            and not self.receber_alert
        ):
            return False

        # Verificar prioridade
        if (
            prioridade == "baixa"
            and not self.receber_baixa
            or prioridade == "media"
            and not self.receber_media
            or prioridade == "alta"
            and not self.receber_alta
            or prioridade == "critica"
            and not self.receber_critica
        ):
            return False

        # Verificar módulo bloqueado
        return not (modulo_origem and modulo_origem in self.modulos_bloqueados)

    def __str__(self):
        return f"Preferências de {self.usuario.username}"

    # --- Signals de criação automática com tolerância a concorrência ---

    class Meta:
        verbose_name = "Preferência de Notificação do Usuário"
        verbose_name_plural = "Preferências de Notificações dos Usuários"


# ================== MODELOS LEGACY/AVANÇADOS (para engine avançada) ==================


class NotificationTemplate(TimestampedModel):
    """Template reutilizável para múltiplos canais (engine avançada)."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    source_module = models.CharField(max_length=50, blank=True, null=True)
    is_global = models.BooleanField(default=False)
    tenant = models.ForeignKey(
        Tenant, blank=True, null=True, on_delete=models.CASCADE, related_name="notification_templates"
    )

    # In-App
    inapp_title = models.CharField(max_length=200, blank=True, null=True)
    inapp_body = models.TextField(blank=True, null=True)

    # Email
    email_subject = models.CharField(max_length=200, blank=True, null=True)
    email_body_html = models.TextField(blank=True, null=True)
    email_body_text = models.TextField(blank=True, null=True)

    # Push
    push_title = models.CharField(max_length=200, blank=True, null=True)
    push_body = models.CharField(max_length=500, blank=True, null=True)

    # SMS
    sms_text = models.CharField(max_length=320, blank=True, null=True)

    def render_email_subject(self, context):
        return self.email_subject or (self.inapp_title or "")

    def render_email_html(self, context):
        return self.email_body_html or f"<p>{self.inapp_body or ''}</p>"

    def render_email_text(self, context):
        return self.email_body_text or (self.inapp_body or "")

    def render_push_title(self, context):
        return self.push_title or (self.inapp_title or "")

    def render_push_body(self, context):
        return self.push_body or (self.inapp_body or "")

    def render_sms_text(self, context):
        return self.sms_text or (self.inapp_body or "")[:160]

    def __str__(self):
        return self.name


class TenantNotificationSettings(TimestampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="notification_settings")
    max_notifications_per_hour = models.PositiveIntegerField(default=200)
    max_notifications_per_day = models.PositiveIntegerField(default=2000)
    enable_auto_grouping = models.BooleanField(default=True)
    grouping_window_minutes = models.PositiveIntegerField(default=5)
    business_hours_start = models.TimeField(blank=True, null=True)
    business_hours_end = models.TimeField(blank=True, null=True)
    default_email_enabled = models.BooleanField(default=True)
    default_sms_enabled = models.BooleanField(default=False)
    default_push_enabled = models.BooleanField(default=True)
    default_inapp_enabled = models.BooleanField(default=True)
    notification_retention_days = models.PositiveIntegerField(default=365)

    def __str__(self):
        return f"Settings {self.tenant_id}"


class UserNotificationPreferences(TimestampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_prefs")
    enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)
    inapp_enabled = models.BooleanField(default=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(blank=True, null=True)
    quiet_hours_end = models.TimeField(blank=True, null=True)
    daily_digest_enabled = models.BooleanField(default=False)
    daily_digest_time = models.TimeField(blank=True, null=True)
    weekly_digest_enabled = models.BooleanField(default=False)
    weekly_digest_day = models.PositiveSmallIntegerField(blank=True, null=True, help_text="0=Segunda ... 6=Domingo")

    def __str__(self):
        return f"Prefs {self.user_id}"


PRIORITY_CHOICES_LEGACY = [("low", "Baixa"), ("medium", "Média"), ("high", "Alta"), ("critical", "Crítica")]


class NotificationAdvanced(TimestampedModel):
    """Modelo avançado usado pelo serviço LegacyNotificationService (multi-destinatário)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="adv_notifications")
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES_LEGACY, default="medium")
    source_module = models.CharField(max_length=50, blank=True, null=True)
    source_object_type = models.CharField(max_length=50, blank=True, null=True)
    source_object_id = models.CharField(max_length=50, blank=True, null=True)
    action_url = models.URLField(blank=True, null=True)
    action_text = models.CharField(max_length=100, blank=True, null=True)
    template = models.ForeignKey("NotificationTemplate", blank=True, null=True, on_delete=models.SET_NULL)
    expiration_date = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=15, default="pending")
    sent_date = models.DateTimeField(blank=True, null=True)
    delivered_date = models.DateTimeField(blank=True, null=True)
    read_date = models.DateTimeField(blank=True, null=True)

    def is_expired(self):
        return self.expiration_date and timezone.now() > self.expiration_date

    def mark_as_sent(self):
        if self.status != "sent":
            self.status = "sent"
            self.save(update_fields=["status"])

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]


class NotificationRecipient(TimestampedModel):
    notification = models.ForeignKey("NotificationAdvanced", on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notification_recipients")
    status = models.CharField(max_length=15, default="pending")
    sent_date = models.DateTimeField(blank=True, null=True)
    delivered_date = models.DateTimeField(blank=True, null=True)
    read_date = models.DateTimeField(blank=True, null=True)
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    inapp_sent = models.BooleanField(default=False)

    def mark_as_sent(self):
        if not self.sent_date:
            self.sent_date = timezone.now()
        self.status = "sent"
        self.save(update_fields=["sent_date", "status"])

    def __str__(self):
        return f"Recipient {self.user_id} notif {self.notification_id}"


class NotificationRule(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="notification_rules")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    source_module = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    conditions = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES_LEGACY, default="medium")
    template = models.ForeignKey("NotificationTemplate", on_delete=models.CASCADE, related_name="rules")
    recipient_type = models.CharField(max_length=30, default="specific_users")
    recipient_config = models.JSONField(default=dict, blank=True)
    escalation_enabled = models.BooleanField(default=False)
    escalation_delay_minutes = models.PositiveIntegerField(default=0)
    escalation_recipients = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Rule {self.name}"


class EmailDelivery(TimestampedModel):
    notification_recipient = models.ForeignKey(
        "NotificationRecipient", on_delete=models.CASCADE, related_name="email_deliveries"
    )
    email_address = models.EmailField()
    sent_date = models.DateTimeField(blank=True, null=True)
    delivery_status = models.CharField(max_length=20, default="pending")
    message_id = models.CharField(max_length=120, blank=True, null=True)
    opened = models.BooleanField(default=False)
    opened_date = models.DateTimeField(blank=True, null=True)
    clicked = models.BooleanField(default=False)
    clicked_date = models.DateTimeField(blank=True, null=True)
    provider = models.CharField(max_length=50, default="internal")
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Email {self.email_address} {self.delivery_status}"


class NotificationMetrics(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="notification_metrics")
    date = models.DateField()
    hour = models.PositiveIntegerField()
    notifications_created = models.PositiveIntegerField(default=0)
    notifications_sent = models.PositiveIntegerField(default=0)
    notifications_delivered = models.PositiveIntegerField(default=0)
    notifications_read = models.PositiveIntegerField(default=0)
    email_sent = models.PositiveIntegerField(default=0)
    email_delivered = models.PositiveIntegerField(default=0)
    email_opened = models.PositiveIntegerField(default=0)
    email_clicked = models.PositiveIntegerField(default=0)
    sms_sent = models.PositiveIntegerField(default=0)
    sms_delivered = models.PositiveIntegerField(default=0)
    push_sent = models.PositiveIntegerField(default=0)
    push_delivered = models.PositiveIntegerField(default=0)
    push_opened = models.PositiveIntegerField(default=0)
    avg_processing_time = models.FloatField(default=0.0)
    avg_delivery_time = models.FloatField(default=0.0)
    bounce_rate = models.FloatField(default=0.0)
    complaint_rate = models.FloatField(default=0.0)
    unsubscribe_rate = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("tenant", "date", "hour")

    def __str__(self):
        return f"Metrics {self.tenant_id} {self.date} {self.hour}"


class NotificationRelatedObject(TimestampedModel):
    """Relação genérica entre a notificação avançada e outros objetos do sistema."""

    notification = models.ForeignKey("NotificationAdvanced", on_delete=models.CASCADE, related_name="related_objects")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=30, default="related")

    def __str__(self):
        return f"Related {self.notification_id} -> {self.content_type_id}:{self.object_id}"

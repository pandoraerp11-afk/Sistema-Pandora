# legacy_notifications/services.py (renomeado logicamente: manter para futura migração)
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import (
    EmailDelivery,
    NotificationMetrics,
    NotificationRecipient,
    NotificationRule,
    TenantNotificationSettings,
    UserNotificationPreferences,
)
from .models import NotificationAdvanced as Notification

logger = logging.getLogger(__name__)
User = get_user_model()


class LegacyNotificationService:
    """Serviço principal para gerenciamento de notificações"""

    @staticmethod
    def create_notification(
        title,
        content,
        tenant,
        recipients=None,
        priority="medium",
        source_module=None,
        source_object_type=None,
        source_object_id=None,
        action_url=None,
        action_text=None,
        template=None,
        expiration_date=None,
    ):
        """Cria uma nova notificação"""

        notification = Notification.objects.create(
            title=title,
            content=content,
            priority=priority,
            source_module=source_module or "system",
            source_object_type=source_object_type or "",
            source_object_id=source_object_id or "",
            action_url=action_url,
            action_text=action_text,
            template=template,
            expiration_date=expiration_date,
            tenant=tenant,
        )

        # Criar destinatários
        if recipients:
            for recipient in recipients:
                if isinstance(recipient, int):
                    try:
                        user = User.objects.get(id=recipient)
                        NotificationRecipient.objects.create(notification=notification, user=user)
                    except User.DoesNotExist:
                        logger.warning(f"Usuário {recipient} não encontrado")
                elif isinstance(recipient, User):
                    NotificationRecipient.objects.create(notification=notification, user=recipient)

        # Processar notificação para envio
        LegacyNotificationService.process_notification(notification)
        return notification

    @staticmethod
    def process_notification(notification):
        """Processa notificação para envio através dos canais apropriados"""
        # Verificar se a notificação não está expirada
        if notification.is_expired():
            notification.status = "expired"
            notification.save()
            return
        # Obter configurações do tenant
        try:
            tenant_settings = TenantNotificationSettings.objects.get(tenant=notification.tenant)
        except TenantNotificationSettings.DoesNotExist:
            tenant_settings = LegacyNotificationService._create_default_tenant_settings(notification.tenant)
        # Verificar limites de frequência
        if not LegacyNotificationService._check_rate_limits(notification, tenant_settings):
            logger.warning(f"Rate limit excedido para tenant {notification.tenant.id}")
            return
        # Processar cada destinatário
        for recipient in notification.recipients.all():
            LegacyNotificationService._process_recipient(recipient, tenant_settings)
        # Atualizar status da notificação
        notification.mark_as_sent()
        # Atualizar métricas
        LegacyNotificationService._update_metrics(notification)

    @staticmethod
    def _process_recipient(recipient, tenant_settings):
        """Processa um destinatário específico"""
        # Obter preferências do usuário
        try:
            user_prefs = UserNotificationPreferences.objects.get(user=recipient.user)
        except UserNotificationPreferences.DoesNotExist:
            user_prefs = LegacyNotificationService._create_default_user_preferences(recipient.user)
        # Verificar se notificações estão habilitadas
        if not user_prefs.enabled:
            return
        # Verificar horário silencioso
        if LegacyNotificationService._is_quiet_hours(user_prefs):
            # Agendar para depois do horário silencioso
            return
        # Enviar através dos canais habilitados
        channels_sent = []

        if user_prefs.email_enabled and tenant_settings.default_email_enabled:
            if LegacyNotificationService._send_email(recipient):
                channels_sent.append("email")
                recipient.email_sent = True

        if user_prefs.sms_enabled and tenant_settings.default_sms_enabled:
            if LegacyNotificationService._send_sms(recipient):
                channels_sent.append("sms")
                recipient.sms_sent = True

        if user_prefs.push_enabled and tenant_settings.default_push_enabled:
            if LegacyNotificationService._send_push(recipient):
                channels_sent.append("push")
                recipient.push_sent = True

        if user_prefs.inapp_enabled and tenant_settings.default_inapp_enabled:
            if LegacyNotificationService._send_inapp(recipient):
                channels_sent.append("inapp")
                recipient.inapp_sent = True

        # Atualizar status do destinatário
        if channels_sent:
            recipient.mark_as_sent()

        logger.info(
            f"Notificação {recipient.notification.id} enviada para {recipient.user.username} via {', '.join(channels_sent)}"
        )

    @staticmethod
    def _send_email(recipient):
        """Envia notificação por e-mail"""
        try:
            notification = recipient.notification
            user = recipient.user

            # Preparar contexto para template
            context = {"notification": notification, "recipient": user, "tenant": notification.tenant, "user": user}

            # Usar template se disponível
            if notification.template:
                subject = notification.template.render_email_subject(context)
                html_content = notification.template.render_email_html(context)
                text_content = notification.template.render_email_text(context)
            else:
                subject = notification.title
                text_content = notification.content
                html_content = f"<p>{notification.content}</p>"

            # Enviar e-mail
            send_mail(
                subject=subject,
                message=text_content,
                html_message=html_content,
                from_email=getattr(notification.tenant, "email_from_address", "noreply@pandoraerp.com"),
                recipient_list=[user.email],
                fail_silently=False,
            )

            # Registrar entrega
            EmailDelivery.objects.create(
                notification_recipient=recipient,
                email_address=user.email,
                delivery_status="sent",
                provider="django_mail",
            )

            return True

        except Exception as e:
            logger.error(f"Erro ao enviar e-mail para {recipient.user.username}: {str(e)}")

            # Registrar falha
            EmailDelivery.objects.create(
                notification_recipient=recipient,
                email_address=recipient.user.email,
                delivery_status="failed",
                provider="django_mail",
                error_message=str(e),
            )

            return False

    @staticmethod
    def _send_sms(recipient):
        """Envia notificação por SMS"""
        try:
            notification = recipient.notification
            user = recipient.user

            # Verificar se usuário tem telefone
            phone = getattr(user, "phone", None)
            if not phone:
                logger.warning(f"Usuário {user.username} não tem telefone cadastrado")
                return False

            # Preparar contexto para template
            context = {"notification": notification, "recipient": user, "tenant": notification.tenant, "user": user}

            # Usar template se disponível
            if notification.template:
                message = notification.template.render_sms_text(context)
            else:
                message = f"{notification.title}: {notification.content}"

            # Truncar mensagem se necessário
            if len(message) > 160:
                message = message[:157] + "..."

            # Aqui seria integrado com provedor de SMS real
            # Por enquanto, apenas log
            logger.info(f"SMS enviado para {phone}: {message}")

            return True

        except Exception as e:
            logger.error(f"Erro ao enviar SMS para {recipient.user.username}: {str(e)}")
            return False

    @staticmethod
    def _send_push(recipient):
        """Envia push notification"""
        try:
            notification = recipient.notification
            user = recipient.user

            # Preparar contexto para template
            context = {"notification": notification, "recipient": user, "tenant": notification.tenant, "user": user}

            # Usar template se disponível
            if notification.template:
                title = notification.template.render_push_title(context)
                body = notification.template.render_push_body(context)
            else:
                title = notification.title
                body = notification.content

            # Aqui seria integrado com serviço de push notifications real
            # Por enquanto, apenas log
            logger.info(f"Push notification enviado para {user.username}: {title} - {body}")

            return True

        except Exception as e:
            logger.error(f"Erro ao enviar push notification para {recipient.user.username}: {str(e)}")
            return False

    @staticmethod
    def _send_inapp(recipient):
        """Marca notificação como disponível in-app"""
        try:
            # Notificações in-app são simplesmente marcadas como enviadas
            # A interface do usuário consultará as notificações através da API
            return True

        except Exception as e:
            logger.error(f"Erro ao processar notificação in-app para {recipient.user.username}: {str(e)}")
            return False

    @staticmethod
    def _check_rate_limits(notification, tenant_settings):
        """Verifica se os limites de frequência foram respeitados"""

        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Verificar limite por hora
        hourly_count = Notification.objects.filter(tenant=notification.tenant, created_at__gte=hour_ago).count()

        if hourly_count >= tenant_settings.max_notifications_per_hour:
            return False

        # Verificar limite por dia
        daily_count = Notification.objects.filter(tenant=notification.tenant, created_at__gte=day_ago).count()

        return not daily_count >= tenant_settings.max_notifications_per_day

    @staticmethod
    def _is_quiet_hours(user_prefs):
        """Verifica se está no horário silencioso do usuário"""

        if not user_prefs.quiet_hours_enabled:
            return False

        if not user_prefs.quiet_hours_start or not user_prefs.quiet_hours_end:
            return False

        now = timezone.now().time()
        start = user_prefs.quiet_hours_start
        end = user_prefs.quiet_hours_end

        if start <= end:
            return start <= now <= end
        else:
            # Horário atravessa meia-noite
            return now >= start or now <= end

    @staticmethod
    def _create_default_tenant_settings(tenant):
        """Cria configurações padrão para o tenant"""
        return TenantNotificationSettings.objects.create(tenant=tenant)

    @staticmethod
    def _create_default_user_preferences(user):
        """Cria preferências padrão para o usuário"""
        return UserNotificationPreferences.objects.create(user=user)

    @staticmethod
    def _update_metrics(notification):
        """Atualiza métricas de notificações cobrindo novos campos."""
        now = timezone.now()
        date = now.date()
        hour = now.hour
        metrics, created = NotificationMetrics.objects.get_or_create(
            tenant=notification.tenant,
            date=date,
            hour=hour,
            defaults={
                "notifications_created": 0,
                "notifications_sent": 0,
                "notifications_delivered": 0,
                "notifications_read": 0,
                "email_sent": 0,
                "email_delivered": 0,
                "email_opened": 0,
                "email_clicked": 0,
                "sms_sent": 0,
                "sms_delivered": 0,
                "push_sent": 0,
                "push_delivered": 0,
                "push_opened": 0,
            },
        )
        metrics.notifications_created += 1
        metrics.notifications_sent += 1
        delivered_count = 0
        read_count = 0
        email_sent = email_delivered = email_opened = email_clicked = 0
        sms_sent = 0
        push_sent = 0
        for recipient in notification.recipients.all():
            if recipient.email_sent:
                email_sent += 1
            if recipient.sms_sent:
                sms_sent += 1
            if recipient.push_sent:
                push_sent += 1
            if recipient.status in ("sent", "delivered", "read"):
                delivered_count += 1 if recipient.delivered_date else 0
            if recipient.read_date:
                read_count += 1
        # Atualizar métricas de entrega/ leitura agregadas
        metrics.notifications_delivered += delivered_count
        metrics.notifications_read += read_count
        metrics.email_sent += email_sent
        metrics.sms_sent += sms_sent
        metrics.push_sent += push_sent
        # Derivar email delivery stats a partir de EmailDelivery relacionados
        related_email_deliveries = EmailDelivery.objects.filter(notification_recipient__notification=notification)
        email_delivered += related_email_deliveries.filter(delivery_status="sent").count()
        email_opened += related_email_deliveries.filter(opened=True).count()
        email_clicked += related_email_deliveries.filter(clicked=True).count()
        metrics.email_delivered += email_delivered
        metrics.email_opened += email_opened
        metrics.email_clicked += email_clicked
        metrics.save()

    @staticmethod
    def process_notification_rules(event_type, source_module, tenant, event_data=None):
        """Processa regras de notificação para um evento específico"""

        rules = NotificationRule.objects.filter(
            tenant=tenant, source_module=source_module, event_type=event_type, active=True
        )

        for rule in rules:
            try:
                # Verificar condições da regra
                if LegacyNotificationService._check_rule_conditions(rule, event_data):
                    # Determinar destinatários
                    recipients = LegacyNotificationService._get_rule_recipients(rule, event_data)

                    if recipients:
                        # Criar notificação baseada na regra
                        LegacyNotificationService.create_notification(
                            title=rule.template.inapp_title,
                            content=rule.template.inapp_body,
                            tenant=tenant,
                            recipients=recipients,
                            priority=rule.priority,
                            source_module=source_module,
                            template=rule.template,
                        )

                        logger.info(f"Notificação criada pela regra {rule.name} para evento {event_type}")

            except Exception as e:
                logger.error(f"Erro ao processar regra {rule.name}: {str(e)}")

    @staticmethod
    def _check_rule_conditions(rule, event_data):
        """Verifica se as condições da regra são atendidas"""

        if not rule.conditions:
            return True

        # Implementação simples de verificação de condições
        # Em produção, usar engine de regras mais sofisticado
        for condition_key, condition_value in rule.conditions.items():
            if event_data and condition_key in event_data:
                if event_data[condition_key] != condition_value:
                    return False
            else:
                return False

        return True

    @staticmethod
    def _get_rule_recipients(rule, event_data):
        """Determina destinatários baseado na configuração da regra"""

        recipients = []

        if rule.recipient_type == "specific_users":
            user_ids = rule.recipient_config.get("user_ids", [])
            recipients = User.objects.filter(id__in=user_ids)

        elif rule.recipient_type == "role_based":
            # Implementar lógica baseada em papéis
            pass

        elif rule.recipient_type == "department_based":
            # Implementar lógica baseada em departamentos
            pass

        elif rule.recipient_type == "dynamic":
            # Implementar lógica dinâmica baseada em event_data
            pass

        return list(recipients)


class LegacyNotificationEventEmitter:
    """Classe para emitir eventos que podem gerar notificações"""

    @staticmethod
    def emit_event(event_type, source_module, tenant, event_data=None):
        """Emite um evento que pode gerar notificações"""

        try:
            LegacyNotificationService.process_notification_rules(
                event_type=event_type, source_module=source_module, tenant=tenant, event_data=event_data
            )
        except Exception as e:
            logger.error(f"Erro ao processar evento {event_type} do módulo {source_module}: {str(e)}")


# Funções de conveniência para uso em outros módulos
def legacy_create_notification(title, content, tenant, recipients=None, **kwargs):
    """(LEGACY) Função de conveniência para criar notificação"""
    return LegacyNotificationService.create_notification(
        title=title, content=content, tenant=tenant, recipients=recipients, **kwargs
    )


def legacy_emit_event(event_type, source_module, tenant, event_data=None):
    """(LEGACY) Função de conveniência para emitir evento"""
    return LegacyNotificationEventEmitter.emit_event(
        event_type=event_type, source_module=source_module, tenant=tenant, event_data=event_data
    )

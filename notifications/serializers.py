# notifications/serializers.py
import contextlib

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    EmailDelivery,
    Notification,
    NotificationMetrics,
    NotificationRecipient,
    NotificationRelatedObject,
    NotificationRule,
    NotificationTemplate,
    TenantNotificationSettings,
    UserNotificationPreferences,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer para usuários (simplificado)"""

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer para templates de notificação"""

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "description",
            "category",
            "source_module",
            "email_subject",
            "email_body_html",
            "email_body_text",
            "sms_text",
            "push_title",
            "push_body",
            "inapp_title",
            "inapp_body",
            "is_global",
            "tenant",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class NotificationRecipientSerializer(serializers.ModelSerializer):
    """Serializer para destinatários de notificação"""

    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = NotificationRecipient
        fields = [
            "id",
            "notification",
            "user",
            "user_details",
            "status",
            "sent_date",
            "delivered_date",
            "read_date",
            "email_sent",
            "sms_sent",
            "push_sent",
            "inapp_sent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "sent_date", "delivered_date", "read_date"]


class NotificationRelatedObjectSerializer(serializers.ModelSerializer):
    """Serializer para objetos relacionados a notificações"""

    class Meta:
        model = NotificationRelatedObject
        fields = ["id", "notification", "content_type", "object_id", "relationship_type"]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer para notificações"""

    recipients_details = NotificationRecipientSerializer(source="recipients", many=True, read_only=True)
    template_details = NotificationTemplateSerializer(source="template", read_only=True)
    related_objects = NotificationRelatedObjectSerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "content",
            "priority",
            "status",
            "expiration_date",
            "sent_date",
            "delivered_date",
            "read_date",
            "source_module",
            "source_object_type",
            "source_object_id",
            "action_url",
            "action_text",
            "template",
            "template_details",
            "tenant",
            "recipients_details",
            "related_objects",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "sent_date", "delivered_date", "read_date"]


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de notificações"""

    recipients = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    related_objects = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Notification
        fields = [
            "title",
            "content",
            "priority",
            "expiration_date",
            "source_module",
            "source_object_type",
            "source_object_id",
            "action_url",
            "action_text",
            "template",
            "tenant",
            "recipients",
            "related_objects",
        ]

    def create(self, validated_data):
        recipients_data = validated_data.pop("recipients", [])
        related_objects_data = validated_data.pop("related_objects", [])

        notification = Notification.objects.create(**validated_data)

        # Criar destinatários
        for user_id in recipients_data:
            try:
                user = User.objects.get(id=user_id)
                NotificationRecipient.objects.create(notification=notification, user=user)
            except User.DoesNotExist:
                pass

        # Criar objetos relacionados
        for related_object in related_objects_data:
            with contextlib.suppress(Exception):
                NotificationRelatedObject.objects.create(
                    notification=notification,
                    content_type_id=related_object.get("content_type"),
                    object_id=related_object.get("object_id"),
                    relationship_type=related_object.get("relationship_type", "related"),
                )

        return notification


class TenantNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer para configurações de notificação por tenant"""

    class Meta:
        model = TenantNotificationSettings
        fields = [
            "id",
            "tenant",
            "max_notifications_per_hour",
            "max_notifications_per_day",
            "enable_auto_grouping",
            "grouping_window_minutes",
            "business_hours_start",
            "business_hours_end",
            "default_email_enabled",
            "default_sms_enabled",
            "default_push_enabled",
            "default_inapp_enabled",
            "notification_retention_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserNotificationPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferências de notificação por usuário"""

    class Meta:
        model = UserNotificationPreferences
        fields = [
            "id",
            "user",
            "enabled",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
            "email_enabled",
            "sms_enabled",
            "push_enabled",
            "inapp_enabled",
            "daily_digest_enabled",
            "daily_digest_time",
            "weekly_digest_enabled",
            "weekly_digest_day",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class NotificationRuleSerializer(serializers.ModelSerializer):
    """Serializer para regras de notificação"""

    template_details = NotificationTemplateSerializer(source="template", read_only=True)

    class Meta:
        model = NotificationRule
        fields = [
            "id",
            "name",
            "description",
            "source_module",
            "event_type",
            "conditions",
            "template",
            "template_details",
            "priority",
            "recipient_type",
            "recipient_config",
            "escalation_enabled",
            "escalation_delay_minutes",
            "escalation_recipients",
            "tenant",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class EmailDeliverySerializer(serializers.ModelSerializer):
    """Serializer para entregas de e-mail"""

    class Meta:
        model = EmailDelivery
        fields = [
            "id",
            "notification_recipient",
            "email_address",
            "sent_date",
            "delivery_status",
            "message_id",
            "opened",
            "opened_date",
            "clicked",
            "clicked_date",
            "provider",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "sent_date", "opened_date", "clicked_date"]


class NotificationMetricsSerializer(serializers.ModelSerializer):
    """Serializer para métricas de notificações"""

    class Meta:
        model = NotificationMetrics
        fields = [
            "id",
            "tenant",
            "date",
            "hour",
            "notifications_created",
            "notifications_sent",
            "notifications_delivered",
            "notifications_read",
            "email_sent",
            "email_delivered",
            "email_opened",
            "email_clicked",
            "sms_sent",
            "sms_delivered",
            "push_sent",
            "push_delivered",
            "push_opened",
            "avg_processing_time",
            "avg_delivery_time",
            "bounce_rate",
            "complaint_rate",
            "unsubscribe_rate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class NotificationBatchActionSerializer(serializers.Serializer):
    """Serializer para ações em lote em notificações"""

    ids = serializers.ListField(child=serializers.IntegerField(), required=True)

    operation = serializers.ChoiceField(choices=["mark_as_read", "mark_as_unread", "delete"], required=True)

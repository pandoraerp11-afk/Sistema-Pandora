# notifications/webhooks.py
import hashlib
import hmac
import json
import logging

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import EmailDelivery, NotificationRecipient

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def email_status_webhook(request):
    """Webhook para receber atualizações de status de e-mail de provedores externos"""

    # Verificar assinatura (exemplo para segurança)
    signature = request.headers.get("X-Webhook-Signature", "")
    if not _verify_webhook_signature(request.body, signature, "email"):
        return HttpResponse(status=401)

    try:
        data = json.loads(request.body)

        # Processar dados específicos do provedor
        # Este exemplo assume um formato genérico, adaptar para provedores específicos

        message_id = data.get("message_id")
        event = data.get("event")
        recipient = data.get("recipient")

        if not message_id or not event or not recipient:
            logger.warning("Webhook de e-mail recebido com dados incompletos")
            return HttpResponse(status=400)

        # Buscar entrega de e-mail correspondente
        try:
            delivery = EmailDelivery.objects.get(message_id=message_id)
        except EmailDelivery.DoesNotExist:
            logger.warning(f"Entrega de e-mail não encontrada para message_id: {message_id}")
            return HttpResponse(status=404)

        # Atualizar status baseado no evento
        if event == "delivered":
            delivery.delivery_status = "delivered"

            # Atualizar status do destinatário
            notification_recipient = delivery.notification_recipient
            notification_recipient.mark_as_delivered()

        elif event == "opened":
            delivery.opened = True
            delivery.opened_date = timezone.now()

        elif event == "clicked":
            delivery.clicked = True
            delivery.clicked_date = timezone.now()

        elif event == "bounced":
            delivery.delivery_status = "bounced"
            delivery.error_message = data.get("reason", "Unknown bounce reason")

        elif event == "complained":
            delivery.delivery_status = "complained"

        delivery.save()

        logger.info(f"Webhook de e-mail processado: {event} para {recipient}")
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON do webhook de e-mail")
        return HttpResponse(status=400)

    except Exception as e:
        logger.error(f"Erro ao processar webhook de e-mail: {str(e)}")
        return HttpResponse(status=500)


@csrf_exempt
@require_POST
def sms_status_webhook(request):
    """Webhook para receber atualizações de status de SMS de provedores externos"""

    # Verificar assinatura (exemplo para segurança)
    signature = request.headers.get("X-Webhook-Signature", "")
    if not _verify_webhook_signature(request.body, signature, "sms"):
        return HttpResponse(status=401)

    try:
        data = json.loads(request.body)

        # Processar dados específicos do provedor
        # Este exemplo assume um formato genérico, adaptar para provedores específicos

        message_id = data.get("message_id")
        event = data.get("event")
        recipient = data.get("recipient")

        if not message_id or not event or not recipient:
            logger.warning("Webhook de SMS recebido com dados incompletos")
            return HttpResponse(status=400)

        # Aqui seria implementada a lógica para atualizar o status do SMS
        # Como não temos um modelo específico para entregas de SMS, este é um exemplo simplificado

        if event == "delivered":
            # Buscar destinatário por algum identificador no message_id
            # Este é um exemplo simplificado, adaptar para implementação real
            try:
                # Assumindo que message_id contém um identificador do destinatário
                recipient_id = message_id.split("-")[0]
                notification_recipient = NotificationRecipient.objects.get(id=recipient_id)
                notification_recipient.mark_as_delivered()
                logger.info(f"SMS marcado como entregue para recipient_id: {recipient_id}")
            except Exception as e:
                logger.error(f"Erro ao processar entrega de SMS: {str(e)}")

        logger.info(f"Webhook de SMS processado: {event} para {recipient}")
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON do webhook de SMS")
        return HttpResponse(status=400)

    except Exception as e:
        logger.error(f"Erro ao processar webhook de SMS: {str(e)}")
        return HttpResponse(status=500)


def _verify_webhook_signature(payload, signature, webhook_type):
    """Verifica assinatura de webhook para segurança"""

    # Em produção, usar chaves secretas específicas para cada provedor
    # Este é apenas um exemplo simplificado

    if webhook_type == "email":
        secret = "email_webhook_secret"
    elif webhook_type == "sms":
        secret = "sms_webhook_secret"
    else:
        return False

    # Calcular assinatura esperada
    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Comparar com assinatura recebida
    return hmac.compare_digest(expected_signature, signature)

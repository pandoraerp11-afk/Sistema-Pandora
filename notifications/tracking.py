# notifications/tracking.py
import base64
import json
import logging

from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from .models import EmailDelivery

logger = logging.getLogger(__name__)


def track_email_open(request, tracking_id):
    """Rastreia abertura de e-mail através de pixel transparente"""

    try:
        # Decodificar tracking_id
        delivery_id = _decode_tracking_id(tracking_id)

        if not delivery_id:
            logger.warning(f"ID de rastreamento inválido: {tracking_id}")
            return HttpResponse(status=404)

        # Buscar entrega de e-mail
        try:
            delivery = EmailDelivery.objects.get(id=delivery_id)
        except EmailDelivery.DoesNotExist:
            logger.warning(f"Entrega de e-mail não encontrada para ID: {delivery_id}")
            return HttpResponse(status=404)

        # Atualizar status de abertura
        if not delivery.opened:
            delivery.opened = True
            delivery.opened_date = timezone.now()
            delivery.save()

            logger.info(f"E-mail marcado como aberto: {delivery_id}")

        # Retornar pixel transparente 1x1
        response = HttpResponse(content_type="image/gif")
        response.write(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"))
        return response

    except Exception as e:
        logger.error(f"Erro ao processar rastreamento de abertura de e-mail: {str(e)}")
        return HttpResponse(status=500)


def track_email_click(request, tracking_id):
    """Rastreia clique em link de e-mail e redireciona para URL original"""

    try:
        # Decodificar tracking_id
        data = _decode_tracking_data(tracking_id)

        if not data or "delivery_id" not in data or "url" not in data:
            logger.warning(f"Dados de rastreamento inválidos: {tracking_id}")
            return HttpResponse(status=404)

        delivery_id = data["delivery_id"]
        original_url = data["url"]

        # Buscar entrega de e-mail
        try:
            delivery = EmailDelivery.objects.get(id=delivery_id)
        except EmailDelivery.DoesNotExist:
            logger.warning(f"Entrega de e-mail não encontrada para ID: {delivery_id}")
            return redirect(original_url)  # Redirecionar mesmo assim para não prejudicar usuário

        # Atualizar status de clique
        if not delivery.clicked:
            delivery.clicked = True
            delivery.clicked_date = timezone.now()
            delivery.save()

            logger.info(f"E-mail marcado como clicado: {delivery_id}")

        # Redirecionar para URL original
        return redirect(original_url)

    except Exception as e:
        logger.error(f"Erro ao processar rastreamento de clique em e-mail: {str(e)}")
        return HttpResponse(status=500)


def generate_tracking_id(delivery_id):
    """Gera ID de rastreamento para abertura de e-mail"""
    try:
        # Converter para string e codificar
        data = str(delivery_id)

        # Em produção, usar criptografia mais robusta
        # Este é um exemplo simplificado
        encoded = base64.urlsafe_b64encode(data.encode()).decode()

        return encoded

    except Exception as e:
        logger.error(f"Erro ao gerar ID de rastreamento: {str(e)}")
        return None


def generate_tracking_url(delivery_id, original_url):
    """Gera URL de rastreamento para clique em link de e-mail"""
    try:
        # Criar dicionário com dados
        data = {"delivery_id": delivery_id, "url": original_url}

        # Converter para JSON e codificar
        json_data = json.dumps(data)

        # Em produção, usar criptografia mais robusta
        # Este é um exemplo simplificado
        encoded = base64.urlsafe_b64encode(json_data.encode()).decode()

        return encoded

    except Exception as e:
        logger.error(f"Erro ao gerar URL de rastreamento: {str(e)}")
        return None


def _decode_tracking_id(tracking_id):
    """Decodifica ID de rastreamento"""
    try:
        # Decodificar base64
        decoded = base64.urlsafe_b64decode(tracking_id.encode()).decode()

        # Converter para inteiro
        return int(decoded)

    except Exception as e:
        logger.error(f"Erro ao decodificar ID de rastreamento: {str(e)}")
        return None


def _decode_tracking_data(tracking_id):
    """Decodifica dados de rastreamento"""
    try:
        # Decodificar base64
        decoded = base64.urlsafe_b64decode(tracking_id.encode()).decode()

        # Converter JSON para dicionário
        data = json.loads(decoded)

        return data

    except Exception as e:
        logger.error(f"Erro ao decodificar dados de rastreamento: {str(e)}")
        return None

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ContaCliente

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ContaCliente)
def conta_cliente_post_save(sender, instance, created, **kwargs):
    if created and instance.pode_acessar_portal():
        logger.info("ContaCliente criada %s", instance)
        instance.registrar_acesso()

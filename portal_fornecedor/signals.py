"""
Signals para o portal do fornecedor.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AcessoFornecedor

User = get_user_model()


@receiver(post_save, sender=AcessoFornecedor)
def acesso_fornecedor_post_save(sender, instance, created, **kwargs):
    """
    Actions após criar/atualizar acesso de fornecedor.
    """
    if created:
        # Log da criação do acesso
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Novo acesso criado: {instance.usuario} -> {instance.fornecedor}")

        # Registrar primeiro acesso se portal ativo
        if instance.pode_acessar_portal():
            instance.registrar_acesso()

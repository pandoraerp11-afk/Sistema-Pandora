"""
Signals para o módulo de cotações.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Cotacao, PropostaFornecedor, PropostaFornecedorItem


@receiver(pre_save, sender=Cotacao)
def cotacao_pre_save(sender, instance, **kwargs):
    """
    Validações antes de salvar uma cotação.
    """
    # Gerar código automaticamente se não fornecido
    if not instance.codigo:
        from django.utils.crypto import get_random_string

        year = timezone.now().year
        random_part = get_random_string(6, allowed_chars="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        instance.codigo = f"COT{year}{random_part}"

    # Validar data de encerramento
    if instance.data_encerramento and instance.data_encerramento < instance.data_abertura:
        raise ValueError("Data de encerramento não pode ser anterior à data de abertura")


@receiver(post_save, sender=PropostaFornecedor)
def proposta_post_save(sender, instance, created, **kwargs):
    """
    Actions após salvar uma proposta.
    """
    if created:
        # Criar itens da proposta baseados nos itens da cotação
        for item_cotacao in instance.cotacao.itens.all():
            PropostaFornecedorItem.objects.get_or_create(
                proposta=instance,
                item_cotacao=item_cotacao,
                defaults={
                    "preco_unitario": 0,
                    "prazo_entrega_dias": instance.prazo_entrega_geral or 30,
                },
            )


@receiver(post_save, sender=PropostaFornecedorItem)
def proposta_item_post_save(sender, instance, **kwargs):
    """
    Recalcula total da proposta quando um item é alterado.
    """
    # Evitar loop infinito usando um flag
    if not getattr(instance, "_recalculating", False):
        instance.proposta.calcular_total()
        instance.proposta._recalculating = True
        instance.proposta.save(update_fields=["total_estimado", "updated_at"])
        instance.proposta._recalculating = False

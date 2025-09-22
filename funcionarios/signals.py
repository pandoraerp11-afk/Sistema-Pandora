# funcionarios/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Funcionario, SalarioHistorico


@receiver(post_save, sender=Funcionario)
def criar_historico_salario_inicial(sender, instance, created, **kwargs):
    """
    Cria um registro inicial no histórico salarial quando um funcionário é criado
    """
    if created:
        SalarioHistorico.objects.create(
            tenant=instance.tenant,
            funcionario=instance,
            data_vigencia=instance.data_admissao,
            valor_salario=instance.salario_base,
            motivo_alteracao="Salário inicial na admissão",
        )


@receiver(pre_save, sender=Funcionario)
def atualizar_historico_salario(sender, instance, **kwargs):
    """
    Cria um novo registro no histórico salarial quando o salário base é alterado
    """
    if instance.pk:  # Se o funcionário já existe
        try:
            funcionario_anterior = Funcionario.objects.get(pk=instance.pk)
            if funcionario_anterior.salario_base != instance.salario_base:
                # Salário foi alterado, criar novo registro no histórico
                SalarioHistorico.objects.create(
                    tenant=instance.tenant,
                    funcionario=instance,
                    data_vigencia=timezone.now().date(),
                    valor_salario=instance.salario_base,
                    motivo_alteracao="Alteração salarial",
                )
        except Funcionario.DoesNotExist:
            pass


@receiver(post_save, sender=Funcionario)
def atualizar_numero_dependentes(sender, instance, **kwargs):
    """
    Atualiza automaticamente o número de dependentes do funcionário
    """
    numero_dependentes = instance.dependentes.count()
    if instance.numero_dependentes != numero_dependentes:
        Funcionario.objects.filter(pk=instance.pk).update(numero_dependentes=numero_dependentes)

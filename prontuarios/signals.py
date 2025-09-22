import contextlib

from django.core.files.storage import default_storage
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from notifications.models import Notification

from .models import Anamnese, Atendimento, FotoEvolucao
from .utils import redimensionar_imagem

# Signals ligados a Paciente removidos – modelo eliminado.


@receiver(post_save, sender=Atendimento)
def atendimento_post_save(sender, instance, created, **kwargs):
    """
    Signal executado após salvar um atendimento.
    """
    if created:
        # Criar notificação para o profissional
        with contextlib.suppress(Exception):
            Notification.objects.create(
                tenant=instance.tenant,
                user=instance.profissional,
                title="Atendimento Registrado",
                message=f"Atendimento de {getattr(getattr(instance, 'servico', None), 'nome_servico', 'Serviço')} registrado para cliente ID {getattr(instance.cliente, 'id', None)}.",
                notification_type="success",
            )

    # Verificar se é necessário agendar próximo atendimento
    if getattr(getattr(instance, "servico", None), "intervalo_minimo_sessoes", None):
        from .utils import calcular_proximo_atendimento

        proxima_data = calcular_proximo_atendimento(instance.data_atendimento.date(), instance.servico)

        if proxima_data:
            with contextlib.suppress(Exception):
                Notification.objects.create(
                    tenant=instance.tenant,
                    user=instance.profissional,
                    title="Próximo Atendimento Sugerido",
                    message=f"Próximo atendimento sugerido para {proxima_data.strftime('%d/%m/%Y')}.",
                    notification_type="info",
                    scheduled_for=timezone.make_aware(
                        timezone.datetime.combine(proxima_data, timezone.datetime.min.time())
                    ),
                )


@receiver(post_save, sender=FotoEvolucao)
def foto_evolucao_post_save(sender, instance, created, **kwargs):
    """
    Signal executado após salvar uma foto de evolução.
    """
    if created and instance.imagem:
        # Redimensionar imagem para otimizar armazenamento
        try:
            imagem_redimensionada = redimensionar_imagem(instance.imagem)
            if imagem_redimensionada != instance.imagem:
                # Salvar imagem redimensionada
                nome_arquivo = instance.imagem.name
                instance.imagem.save(nome_arquivo, imagem_redimensionada, save=False)
                instance.save(update_fields=["imagem"])
        except Exception:
            pass  # Falha silenciosa se não conseguir redimensionar

        # Criar notificação
        with contextlib.suppress(Exception):
            Notification.objects.create(
                tenant=instance.tenant,
                title="Nova Foto de Evolução",
                message=f"Nova foto de evolução adicionada para cliente ID {getattr(instance.cliente, 'id', None)}.",
                notification_type="info",
                target_users="admin",
            )


@receiver(post_save, sender=Anamnese)
def anamnese_post_save(sender, instance, created, **kwargs):
    # Simplificado: apenas placeholder para futura lógica ligada a cliente.
    return


# Signals de deleção/backup de Paciente removidos.


@receiver(post_delete, sender=FotoEvolucao)
def foto_evolucao_post_delete(sender, instance, **kwargs):
    """
    Signal executado após deletar uma foto de evolução.
    """
    # Remover arquivo físico da imagem
    if instance.imagem:
        try:
            if default_storage.exists(instance.imagem.name):
                default_storage.delete(instance.imagem.name)
        except Exception:
            pass  # Falha silenciosa se não conseguir deletar o arquivo


@receiver(post_save, sender=Atendimento)
def verificar_intervalo_atendimentos(sender, instance, created, **kwargs):
    """
    Verifica se o intervalo entre atendimentos está sendo respeitado.
    """
    if created and getattr(getattr(instance, "servico", None), "intervalo_minimo_sessoes", None):
        # Buscar último atendimento do mesmo serviço
        ultimo_atendimento = (
            Atendimento.objects.filter(
                cliente=instance.cliente, servico=instance.servico, data_atendimento__lt=instance.data_atendimento
            )
            .order_by("-data_atendimento")
            .first()
        )

        if ultimo_atendimento:
            dias_diferenca = (instance.data_atendimento.date() - ultimo_atendimento.data_atendimento.date()).days

            intervalo_min = getattr(instance.servico, "intervalo_minimo_sessoes", None)
            if intervalo_min and dias_diferenca < intervalo_min:
                with contextlib.suppress(Exception):
                    Notification.objects.create(
                        tenant=instance.tenant,
                        user=instance.profissional,
                        title="Atenção: Intervalo Mínimo",
                        message=f"Atendimento de {getattr(instance.servico, 'nome_servico', 'Serviço')} antes do intervalo mínimo ({intervalo_min} dias).",
                        notification_type="warning",
                    )


@receiver(post_save, sender=Atendimento)
def atualizar_estatisticas_servico(sender, instance, created, **kwargs):
    """Hook para futuras estatísticas agregadas de serviços clínicos."""
    if created:
        # Placeholder: implementar agregações em Servico/perfil_clinico se necessário
        pass


# Validação automática de Paciente removida.

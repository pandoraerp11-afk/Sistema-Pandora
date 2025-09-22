import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver
from django.urls import reverse

from agenda.models import AgendaConfiguracao, Evento

from .models import (
    ConfiguracaoNotificacao,
    LogNotificacao,
    Notification,
    NotificationAdvanced,
    NotificationRecipient,
    PreferenciaUsuarioNotificacao,
)

logger = logging.getLogger(__name__)
User = get_user_model()

# Signals customizados para integração com outros módulos
notificacao_criada = Signal()
notificacao_lida = Signal()
notificacao_arquivada = Signal()


@receiver(post_save, sender=User)
def criar_preferencia_usuario_notificacao(sender, instance, created, **kwargs):
    """Cria preferências de notificação para novos usuários"""
    if created:
        try:
            PreferenciaUsuarioNotificacao.objects.get_or_create(usuario=instance)
            logger.info(f"Preferências de notificação asseguradas para usuário {instance.username}")
        except Exception as e:
            logger.error(f"Erro ao criar preferências de notificação para usuário {instance.username}: {str(e)}")


@receiver(post_save, sender="core.Tenant")
def criar_configuracao_tenant_notificacao(sender, instance, created, **kwargs):
    """Cria configurações de notificação para novos tenants"""
    if created:
        try:
            ConfiguracaoNotificacao.objects.get_or_create(tenant=instance)
            logger.info(f"Configurações de notificação asseguradas para tenant {instance.name}")
            # Criar configuração da Agenda também
            try:
                AgendaConfiguracao.objects.create(tenant=instance, lembretes_padrao=[1440, 120, 15])
                logger.info(f"Configuração da Agenda criada para tenant {instance.name}")
            except Exception as e:
                logger.error(f"Erro ao criar configuração da Agenda para tenant {instance.name}: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao criar configurações de notificação para tenant {instance.name}: {str(e)}")


@receiver(post_save, sender=Notification)
def processar_nova_notificacao(sender, instance, created, **kwargs):
    """Processa novas notificações"""
    if created:
        try:
            # Log da criação
            LogNotificacao.objects.create(
                notificacao=instance, usuario=None, acao=f"Notificação '{instance.titulo}' criada."
            )

            # Disparar signal customizado
            notificacao_criada.send(sender=sender, notificacao=instance)

            logger.info(f"Notificação {instance.id} criada e processada")
        except Exception as e:
            logger.error(f"Erro ao processar nova notificação {instance.id}: {str(e)}")


@receiver(post_save, sender=Notification)
def broadcast_notification_count(sender, instance, created, **kwargs):
    if created:
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            group = f"notif_user_{instance.usuario_destinatario_id}"
            # Contagem atualizada
            count = Notification.objects.filter(
                usuario_destinatario=instance.usuario_destinatario, tenant=instance.tenant, status="nao_lida"
            ).count()
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "notifications.update",
                    "event": "notification_created",
                    "notification_id": instance.id,
                    "unread_count": count,
                    "titulo": instance.titulo,
                    "tipo": instance.tipo,
                    "prioridade": instance.prioridade,
                },
            )
        except Exception:
            pass


# Signal receivers para integração com outros módulos


# Agenda
@receiver(pre_save, sender="agenda.Evento")
def cache_old_evento_values(sender, instance, **kwargs):
    """Antes de salvar, guarda valores antigos para comparação no post_save."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
            instance._old_data_inicio = old.data_inicio
            instance._old_data_fim = old.data_fim
        except sender.DoesNotExist:
            instance._old_status = None
            instance._old_data_inicio = None
            instance._old_data_fim = None
    else:
        instance._old_status = None
        instance._old_data_inicio = None
        instance._old_data_fim = None


@receiver(post_save, sender="agenda.Evento")
def notificar_evento_agenda(sender, instance, created, **kwargs):
    """Cria notificações para eventos da agenda"""
    try:
        if created:
            # Notificar responsável
            if instance.responsavel:
                criar_notificacao_evento(
                    tenant=instance.tenant,
                    usuario=instance.responsavel,
                    evento=instance,
                    tipo="info",
                    titulo=f"Novo evento: {instance.titulo}",
                    mensagem=f"Um novo evento foi criado para {instance.data_inicio.strftime('%d/%m/%Y %H:%M')}.",
                )

            # Notificar participantes
            for participante in instance.participantes.all():
                if participante != instance.responsavel:
                    criar_notificacao_evento(
                        tenant=instance.tenant,
                        usuario=participante,
                        evento=instance,
                        tipo="info",
                        titulo=f"Você foi convidado para: {instance.titulo}",
                        mensagem=f"Você foi convidado para participar do evento em {instance.data_inicio.strftime('%d/%m/%Y %H:%M')}.",
                    )
        else:
            # Detectar mudanças relevantes no evento usando valores cacheados no pre_save
            mensagens = []
            tipo_mensagem = "info"
            old_status = getattr(instance, "_old_status", None)
            old_inicio = getattr(instance, "_old_data_inicio", None)
            old_fim = getattr(instance, "_old_data_fim", None)

            # Mudança de status
            if old_status is not None and old_status != instance.status:
                status_map = {
                    "pendente": ("warning", "Status alterado para Pendente"),
                    "confirmado": ("success", "Status alterado para Confirmado"),
                    "concluido": ("success", "Status alterado para Concluído"),
                    "realizado": ("success", "Status alterado para Realizado"),
                    "cancelado": ("error", "Status alterado para Cancelado"),
                }
                tipo_mensagem, msg = status_map.get(
                    instance.status, ("info", f"Status alterado para {instance.get_status_display()}")
                )
                mensagens.append(msg)

            # Mudança de data/horário
            if (old_inicio and old_inicio != instance.data_inicio) or (old_fim != instance.data_fim):
                mensagens.append(f"Horário atualizado para {instance.data_inicio.strftime('%d/%m/%Y %H:%M')}")

            # Alerta de conflito: outro evento do mesmo responsável que se sobrepõe
            if instance.responsavel_id:
                overlapping = (
                    Evento.objects.filter(
                        tenant=instance.tenant,
                        responsavel_id=instance.responsavel_id,
                    )
                    .exclude(pk=instance.pk)
                    .filter(
                        data_inicio__lt=instance.data_fim or instance.data_inicio,
                        data_fim__gt=instance.data_inicio if instance.data_fim else instance.data_inicio,
                    )
                    .exists()
                )
                if overlapping:
                    mensagens.append("Possível conflito de agenda detectado para o responsável")
                    if tipo_mensagem != "error":
                        tipo_mensagem = "warning"

            if mensagens:
                texto = "; ".join(mensagens)
                for participante in instance.participantes.all():
                    criar_notificacao_evento(
                        tenant=instance.tenant,
                        usuario=participante,
                        evento=instance,
                        tipo=tipo_mensagem,
                        titulo=f"Evento atualizado: {instance.titulo}",
                        mensagem=texto,
                    )
                if instance.responsavel:
                    criar_notificacao_evento(
                        tenant=instance.tenant,
                        usuario=instance.responsavel,
                        evento=instance,
                        tipo=tipo_mensagem,
                        titulo=f"Evento atualizado: {instance.titulo}",
                        mensagem=texto,
                    )
    except Exception as e:
        logger.error(f"Erro ao criar notificação para evento {instance.id}: {str(e)}")


def criar_notificacao_evento(tenant, usuario, evento, tipo, titulo, mensagem):
    """Helper para criar notificações de eventos"""
    # Verificar preferências do usuário
    try:
        preferencia = usuario.preferencia_notificacao
        if not preferencia.deve_receber_notificacao(tipo, "media", "agenda"):
            return
    except PreferenciaUsuarioNotificacao.DoesNotExist:
        pass  # Se não tem preferência, criar a notificação

    # Construir URL de ação com reverse para manter robustez
    try:
        url = reverse("agenda:evento_detail", args=[evento.id])
    except Exception:
        # Fallback para rota alternativa
        try:
            url = reverse("agenda:evento_detail_alt", args=[evento.id])
        except Exception:
            url = f"/agenda/evento/{evento.id}/"

    Notification.objects.create(
        tenant=tenant,
        usuario_destinatario=usuario,
        titulo=titulo,
        mensagem=mensagem,
        tipo=tipo,
        prioridade="media",
        modulo_origem="agenda",
        evento_origem="evento_criado_atualizado",
        url_acao=url,
        dados_extras={
            "evento_id": evento.id,
            "evento_titulo": evento.titulo,
            "data_inicio": evento.data_inicio.isoformat(),
        },
    )
    if getattr(settings, "USE_ADVANCED_NOTIFICATIONS", True):
        try:
            adv = NotificationAdvanced.objects.create(
                tenant=tenant,
                title=titulo,
                content=mensagem,
                priority="medium",
                source_module="agenda",
                source_object_type="Evento",
                source_object_id=str(evento.id),
                action_url=url,
            )
            NotificationRecipient.objects.create(notification=adv, user=usuario)
        except Exception:
            pass


# Chat
@receiver(post_save, sender="chat.Mensagem")
def notificar_nova_mensagem_chat(sender, instance, created, **kwargs):
    """Cria notificações para novas mensagens do chat"""
    if created:
        try:
            # Notificar todos os participantes da conversa, exceto o remetente
            conversa = instance.conversa
            try:
                url_conversa = reverse("chat:conversa_detail", args=[conversa.id])
            except Exception:
                url_conversa = f"/chat/conversas/{conversa.id}/"

            # Importar aqui para evitar ciclos
            from chat.models import ParticipanteConversa

            participantes = conversa.participantes.exclude(id=instance.remetente_id)
            for usuario in participantes:
                # Respeitar configuração por participante na conversa
                try:
                    pc = ParticipanteConversa.objects.get(conversa=conversa, usuario=usuario)
                    if not pc.ativo or not pc.notificacoes_habilitadas:
                        continue
                except ParticipanteConversa.DoesNotExist:
                    continue

                # Respeitar preferências globais do usuário
                try:
                    preferencia = usuario.preferencia_notificacao
                    if not preferencia.deve_receber_notificacao("info", "media", "chat"):
                        continue
                except PreferenciaUsuarioNotificacao.DoesNotExist:
                    pass

                Notification.objects.create(
                    tenant=instance.tenant,
                    usuario_destinatario=usuario,
                    titulo=f"Nova mensagem de {instance.remetente.username}",
                    mensagem=(instance.conteudo[:100] + "...")
                    if instance.conteudo and len(instance.conteudo) > 100
                    else (instance.conteudo or "Arquivo enviado"),
                    tipo="info",
                    prioridade="media",
                    modulo_origem="chat",
                    evento_origem="mensagem_recebida",
                    url_acao=url_conversa,
                    dados_extras={
                        "mensagem_id": instance.id,
                        "remetente": instance.remetente.username,
                        "conversa_id": conversa.id,
                    },
                )
                if getattr(settings, "USE_ADVANCED_NOTIFICATIONS", True):
                    try:
                        adv = NotificationAdvanced.objects.create(
                            tenant=instance.tenant,
                            title=f"Nova mensagem de {instance.remetente.username}",
                            content=(instance.conteudo[:500] + "...")
                            if instance.conteudo and len(instance.conteudo) > 500
                            else (instance.conteudo or "Arquivo enviado"),
                            priority="medium",
                            source_module="chat",
                            source_object_type="Mensagem",
                            source_object_id=str(instance.id),
                            action_url=url_conversa,
                        )
                        NotificationRecipient.objects.create(notification=adv, user=usuario)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Erro ao criar notificação para mensagem {instance.id}: {str(e)}")


# Outros módulos podem ser adicionados aqui seguindo o mesmo padrão
# Exemplo: Compras, Aprovações, etc.

# Removido uso direto de ContentType aqui para compatibilidade com o modelo atual de Notification

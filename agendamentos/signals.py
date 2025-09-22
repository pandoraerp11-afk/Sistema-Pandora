from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from agenda.models import Evento

from .models import Agendamento


@receiver(post_save, sender=Agendamento)
def criar_evento_agendamento(sender, instance: Agendamento, created, **kwargs):
    """Cria/atualiza Evento na agenda compartilhada para cada agendamento confirmado.
    Evita duplicar se já existir metadata['evento_agenda_id'].
    """
    if not getattr(settings, "ENABLE_EVENT_MIRROR", True):
        return
    if instance.status not in ("CONFIRMADO", "EM_ANDAMENTO", "CANCELADO", "CONCLUIDO"):
        return
    ev_id = instance.metadata.get("evento_agenda_id") if isinstance(instance.metadata, dict) else None
    # Usar apenas nome do serviço
    serv_nome = getattr(instance, "servico", None)
    serv_nome = getattr(serv_nome, "nome_servico", None) if serv_nome else None
    base_nome = serv_nome or "Serviço"
    titulo = f"Agendamento: {base_nome} - {getattr(instance.cliente, 'nome_display', '')}"
    data_inicio = instance.data_inicio
    data_fim = instance.data_fim
    if ev_id:
        try:
            ev = Evento.objects.get(id=ev_id, tenant=instance.tenant)
            # Se cancelado, marcar evento como cancelado e sair
            if instance.status == "CANCELADO":
                ev.status = "cancelado"
                ev.save(update_fields=["status"])
                return
            # Atualização normal
            ev.titulo = titulo
            ev.data_inicio = data_inicio
            ev.data_fim = data_fim
            ev.status = "concluido" if instance.status == "CONCLUIDO" else "confirmado"
            # Padronizar tipo_evento para 'servico' (compat com legado 'procedimento')
            ev.tipo_evento = "servico"
            ev.responsavel = instance.profissional
            ev.save(update_fields=["titulo", "data_inicio", "data_fim", "status", "tipo_evento", "responsavel"])
            return
        except Evento.DoesNotExist:
            pass
    ev = Evento.objects.create(
        tenant=instance.tenant,
        titulo=titulo,
        descricao=f"Agendamento originado pelo módulo beta. ID {instance.id}",
        data_inicio=data_inicio,
        data_fim=data_fim,
        status="confirmado",
        tipo_evento="servico",
        responsavel=instance.profissional,
    )
    # Persistir id no metadata (sem recriar migração usando update_fields para otimizar)
    meta = instance.metadata or {}
    if "evento_agenda_id" not in meta or meta.get("evento_agenda_id") != ev.id:
        meta["evento_agenda_id"] = ev.id
        instance.metadata = meta
        instance.save(update_fields=["metadata"])

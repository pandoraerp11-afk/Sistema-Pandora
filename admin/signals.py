# admin/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Tenant, TenantUser

from .models import TenantConfiguration
from .utils import create_system_alert  # Usando a função helper que já revisamos


@receiver(post_save, sender=Tenant)
def tenant_created_or_updated(sender, instance, created, **kwargs):
    """
    Sinal disparado quando um tenant é criado ou atualizado.
    Automatiza a criação de configurações e alertas.
    """
    if created:
        # Garante que toda nova empresa tenha um registro de configuração padrão.
        TenantConfiguration.objects.get_or_create(tenant=instance)

        # Cria um alerta para notificar os superusuários sobre a nova empresa.
        # CORREÇÃO: Trocado 'slug' por 'subdomain' para corresponder ao modelo.
        create_system_alert(
            title=f"Nova empresa criada: {instance.name}",
            description=f"Uma nova empresa foi criada com o nome {instance.name} e subdomínio {instance.subdomain}.",
            severity="medium",
            alert_type="tenant",
            tenant=instance,
            metadata={"tenant_id": instance.id, "tenant_subdomain": instance.subdomain},
        )
    # Se você usa django-simple-history ou similar, pode verificar mudanças.
    # Esta lógica depende de um `tracker` no objeto, que não é padrão do Django.
    elif hasattr(instance, "tracker") and instance.tracker.has_changed("status"):
        old_status = instance.tracker.previous("status")
        new_status = instance.status

        # CORREÇÃO: Trocado 'slug' por 'subdomain'
        create_system_alert(
            title=f"Status da empresa alterado: {instance.name}",
            description=f"O status da empresa {instance.name} foi alterado de '{old_status}' para '{new_status}'.",
            severity="high",
            alert_type="tenant",
            tenant=instance,
            metadata={
                "tenant_id": instance.id,
                "tenant_subdomain": instance.subdomain,
                "old_status": old_status,
                "new_status": new_status,
            },
        )


@receiver(post_save, sender=TenantUser)
def tenant_user_created_or_updated(sender, instance, created, **kwargs):
    """
    Sinal disparado quando um vínculo usuário-empresa é criado ou atualizado.
    Cria alertas de segurança para mudanças de privilégio.
    """
    # CORREÇÃO: A verificação agora usa o campo booleano 'is_tenant_admin', que é mais robusto.
    # Se o vínculo foi criado e o usuário JÁ É um admin, ou se o status de admin mudou.
    is_newly_made_admin = False
    if created and instance.is_tenant_admin:
        is_newly_made_admin = True

    # Verifica se o campo 'is_tenant_admin' foi alterado de False para True
    if not created and hasattr(instance, "tracker") and instance.tracker.has_changed("is_tenant_admin"):
        if instance.tracker.previous("is_tenant_admin") is False and instance.is_tenant_admin is True:
            is_newly_made_admin = True

    if is_newly_made_admin:
        user_name = instance.user.get_full_name() or instance.user.username
        # CORREÇÃO: Trocado 'slug' por 'subdomain' na metadata.
        create_system_alert(
            title=f"Novo privilégio de Admin: {instance.tenant.name}",
            description=f"O usuário '{user_name}' recebeu privilégios de administrador na empresa '{instance.tenant.name}'.",
            severity="high",  # Promoção a admin é um evento de alta importância
            alert_type="security",
            tenant=instance.tenant,
            metadata={
                "tenant_id": instance.tenant.id,
                "tenant_subdomain": instance.tenant.subdomain,
                "user_id": instance.user.id,
                "username": instance.user.username,
            },
        )


# NOTA: O sinal para TenantMetrics e SystemAlert foi mantido no seu arquivo original
# e não precisa de alterações relacionadas à estrutura de Tenant/User,
# então não foi incluído aqui para manter o foco na correção principal.
# Se precisar deles, posso adicioná-los de volta.

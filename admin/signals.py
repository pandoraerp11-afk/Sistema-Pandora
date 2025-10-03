# admin/signals.py
"""Sinais para o módulo de administração."""

from typing import Any

from django.db.models.base import Model
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Tenant, TenantUser

from .models import TenantConfiguration
from .utils import SystemAlertData, create_system_alert


@receiver(post_save, sender=Tenant)
def tenant_created_or_updated(
    _sender: type[Model],
    instance: Tenant,
    created: bool,  # noqa: FBT001
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """Dispara ações quando um Tenant é criado ou atualizado.

    Args:
        instance: A instância do modelo.
        created: True se um novo registro foi criado.

    """
    if created:
        # Garante que toda nova empresa tenha um registro de configuração padrão.
        TenantConfiguration.objects.get_or_create(tenant=instance)

        # Cria um alerta para notificar os superusuários sobre a nova empresa.
        alert_data = SystemAlertData(
            title=f"Nova empresa criada: {instance.name}",
            description=f"Uma nova empresa foi criada com o nome {instance.name} e subdomínio {instance.subdomain}.",
            severity="medium",
            alert_type="tenant",
            tenant=instance,
            metadata={"tenant_id": instance.id, "tenant_subdomain": instance.subdomain},
        )
        create_system_alert(alert_data)

    # Esta lógica depende de um `tracker` no objeto, que não é padrão do Django.
    elif hasattr(instance, "tracker") and instance.tracker.has_changed("status"):
        old_status = instance.tracker.previous("status")
        new_status = instance.status

        alert_data = SystemAlertData(
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
        create_system_alert(alert_data)


@receiver(post_save, sender=TenantUser)
def tenant_user_created_or_updated(
    _sender: type[Model],
    instance: TenantUser,
    created: bool,  # noqa: FBT001
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """Dispara ações quando um TenantUser é criado ou atualizado.

    Args:
        instance: A instância do modelo.
        created: True se um novo registro foi criado.

    """
    is_newly_made_admin = False
    if created and instance.is_tenant_admin:
        is_newly_made_admin = True

    if (
        not created
        and hasattr(instance, "tracker")
        and instance.tracker.has_changed("is_tenant_admin")
        and instance.tracker.previous("is_tenant_admin") is False
        and instance.is_tenant_admin is True
    ):
        is_newly_made_admin = True

    if is_newly_made_admin:
        user_name = instance.user.get_full_name() or instance.user.username
        alert_data = SystemAlertData(
            title=f"Novo privilégio de Admin: {instance.tenant.name}",
            description=(
                f"O usuário '{user_name}' recebeu privilégios de administrador na empresa '{instance.tenant.name}'."
            ),
            severity="high",
            alert_type="security",
            tenant=instance.tenant,
            metadata={
                "tenant_id": instance.tenant.id,
                "tenant_subdomain": instance.tenant.subdomain,
                "user_id": instance.user.id,
                "username": instance.user.username,
            },
        )
        create_system_alert(alert_data)

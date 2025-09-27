"""Módulo para permissões de UI."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING

from core.models import TenantUser

from .permission_resolver import has_permission as resolver_has_permission

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from cadastros_gerais.models import Tenant
    from user_management.models import Role

logger = logging.getLogger(__name__)


def _get_role(user: User, tenant: Tenant) -> Role | None:
    try:
        tu = TenantUser.objects.select_related("role").get(user=user, tenant=tenant)
    except TenantUser.DoesNotExist:
        return None
    else:
        return tu.role


def _role_has_model_perm(role: Role | None, app_label: str, model_name: str, action: str) -> bool:
    if not role:
        return False
    with suppress(Exception):  # Erros aqui não devem quebrar a UI
        codename = f"{action.lower()}_{model_name.lower()}"
        return role.permissions.filter(content_type__app_label=app_label, codename=codename).exists()
    return False


def _resolver_allows(user: User, tenant: Tenant, action: str, resource: str | None = None) -> bool:
    with suppress(Exception):  # Falhas no resolver não devem quebrar a UI
        return bool(resolver_has_permission(user, tenant, action, resource))
    return False


def build_ui_permissions(  # noqa: PLR0913
    user: User,
    tenant: Tenant,
    *,
    module_key: str | None = None,
    app_label: str | None = None,
    model_name: str | None = None,
    resource: str | None = None,
) -> dict[str, bool]:
    """Retorna um dicionário com permissões de UI padronizadas.

    Chaves retornadas:
      - can_view, can_add, can_edit, can_delete

    Estratégia:
      1) Superuser: tudo True
      2) Se module_key for fornecido, usa PermissionResolver (ações VIEW_/CREATE_/EDIT_/DELETE_)
      3) Caso contrário e se app_label/model_name forem fornecidos, usa permissões Django no Role do tenant
      4) Fallback conservador: False
    """
    perms = {"can_view": False, "can_add": False, "can_edit": False, "can_delete": False}

    if not user or not getattr(user, "is_authenticated", False):
        return perms

    if getattr(user, "is_superuser", False):
        return dict.fromkeys(perms, True)

    # Se for admin do tenant, conceder permissões amplas na UI
    with suppress(Exception):  # Falhas de DB não devem quebrar a UI
        if (
            tenant
            and not getattr(user, "is_superuser", False)
            and TenantUser.objects.filter(user=user, tenant=tenant, is_tenant_admin=True).exists()
        ):
            return dict.fromkeys(perms, True)

    # Tentar via PermissionResolver se module_key existir
    if module_key and tenant:
        key = module_key.upper()
        perms["can_view"] = _resolver_allows(user, tenant, f"VIEW_{key}", resource)
        # Para adicionar, usamos CREATE_
        perms["can_add"] = _resolver_allows(user, tenant, f"CREATE_{key}", resource)
        perms["can_edit"] = _resolver_allows(user, tenant, f"EDIT_{key}", resource)
        perms["can_delete"] = _resolver_allows(user, tenant, f"DELETE_{key}", resource)

        # Se ao menos uma chave foi resolvida True/False de forma determinística, retornamos resultado
        # (mesmo que todas False: mantém comportamento explícito)
        return perms

    # Caso sem module_key, fazer bridging para Django Permissions no Role
    if tenant and app_label and model_name:
        role = _get_role(user, tenant)
        perms["can_view"] = _role_has_model_perm(role, app_label, model_name, "view")
        perms["can_add"] = _role_has_model_perm(role, app_label, model_name, "add")
        perms["can_edit"] = _role_has_model_perm(role, app_label, model_name, "change")
        perms["can_delete"] = _role_has_model_perm(role, app_label, model_name, "delete")
        return perms

    return perms

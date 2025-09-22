"""Wrapper legado (DEPRECATED) – mantido apenas para compatibilidade temporária.

Este módulo delega para o resolver unificado em ``shared.services.permission_resolver``.
REMOVER após confirmar inexistência de imports residuais em ambos ambientes de desenvolvimento.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from shared.services.permission_resolver import has_permission as _shared_has_permission  # type: ignore
except Exception:  # pragma: no cover
    _shared_has_permission = None  # type: ignore
    logger.exception("Resolver unificado indisponível – verifique instalação de 'shared'.")


def user_has_permission(
    user, modulo: str, acao: str, recurso: str | None = None, scope_tenant_id: int | None = None, request=None
) -> bool:  # noqa: D401
    """Interface antiga: (user, modulo, acao, recurso?, scope_tenant_id?).

    Converte para o formato de ação esperado pelo resolver novo: ``ACAO_MODULO`` (upper).
    Mantém semântica básica: recurso é passado se fornecido.
    """
    if _shared_has_permission is None:
        return False
    # Normaliza ação no formato usado pelo resolver novo (ex: view_dashboard -> VIEW_DASHBOARD)
    action = f"{acao}_{modulo}".upper()
    # scope_tenant_id é obrigatório para o resolver unificado – se ausente, nega por segurança
    if scope_tenant_id is None:
        return False
    # Recupera tenant dinamicamente apenas quando necessário (lazy import)
    from core.models import Tenant

    try:
        tenant = Tenant.objects.get(id=scope_tenant_id)
    except Tenant.DoesNotExist:
        return False
    return _shared_has_permission(user, tenant, action, recurso)


# Alias compatível com código que importava a classe antiga
class PermissionResolver:  # pragma: no cover - wrapper fino
    """Mantido por compatibilidade (deprecated). Use shared.services.permission_resolver.PermissionResolver."""

    def __init__(self, user, scope_tenant_id: int | None = None, request_cache=None, use_cache: bool = True):
        self.user = user
        self.scope_tenant_id = scope_tenant_id

    def has_permission(self, modulo: str, acao: str, recurso: str | None = None) -> bool:
        return user_has_permission(self.user, modulo, acao, recurso, self.scope_tenant_id)


__all__ = ["user_has_permission", "PermissionResolver"]

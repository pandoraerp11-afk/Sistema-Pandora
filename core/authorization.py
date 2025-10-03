"""Camada central de autorização modular.

IMPORTANTE: Não remover funções legadas antes de validar usos.
Esta camada será usada gradualmente (feature flag) pelo menu e middleware.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.http import HttpRequest

    from .models import Tenant

try:
    import prometheus_client as _prom

    _PROM_ENABLED = True
except ImportError:  # pragma: no cover
    _prom = None
    _PROM_ENABLED = False

logger = logging.getLogger(__name__)

# Métricas Prometheus
if _PROM_ENABLED and _prom:
    MODULE_DENY_COUNTER = _prom.Counter(
        "pandora_module_denials_total",
        "Total de negações de acesso a módulos.",
        ["module", "reason"],
    )
else:  # pragma: no cover
    MODULE_DENY_COUNTER = None

# Razões padronizadas
REASON_OK = "OK"
REASON_NO_TENANT = "NO_TENANT"
REASON_SUPERUSER = "SUPERUSER_BYPASS"
REASON_MODULE_NAME_EMPTY = "MODULE_NAME_EMPTY"
REASON_MODULE_DISABLED = "MODULE_DISABLED_FOR_TENANT"
REASON_PORTAL_DENY = "PORTAL_NOT_IN_WHITELIST"
REASON_UNKNOWN_ERROR = "UNKNOWN_ERROR"
REASON_RESOLVER_DENY = "PERMISSION_RESOLVER_DENY"

PORTAL_USER_GROUP_NAME = getattr(settings, "PORTAL_USER_GROUP_NAME", "PortalUser")
DEFAULT_DEDUP_SECONDS = 0


@dataclass(frozen=True)
class AccessDecision:
    """Representa o resultado de uma verificação de acesso."""

    allowed: bool
    reason: str = REASON_OK


def is_portal_user(user: AbstractBaseUser | AnonymousUser | None) -> bool:
    """Verifica de forma não invasiva se um usuário é do tipo portal.

    Ordem de verificação:
    1. Campo `user.user_type == 'PORTAL'`
    2. Atributo dinâmico `user.is_portal_user is True`
    3. Pertence ao grupo Django 'PortalUser'
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "user_type", None) == "PORTAL":
        return True
    if getattr(user, "is_portal_user", False):
        return True

    try:
        return user.groups.filter(name=PORTAL_USER_GROUP_NAME).exists()
    except (AttributeError, TypeError):
        # Se o objeto de usuário não tiver `groups` ou for de um tipo inesperado.
        return False


def _parse_enabled_modules(raw_modules: str | list | dict | None) -> list[str]:
    """Interpreta o valor de 'enabled_modules' que pode ser string JSON, lista ou dict."""
    if isinstance(raw_modules, list):
        return raw_modules
    if isinstance(raw_modules, str):
        try:
            parsed = json.loads(raw_modules)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    if isinstance(raw_modules, dict):
        # Formato legado onde os módulos estão sob a chave "modules"
        modules = raw_modules.get("modules")
        return modules if isinstance(modules, list) else []
    return []


def _tenant_has_module(tenant: Tenant, module_name: str) -> bool:
    """Verifica se um módulo está habilitado para o tenant.

    Compatível com múltiplos formatos do campo enabled_modules (dict/list/str JSON)
    e com a API canônica tenant.is_module_enabled. Se a API canônica retornar
    True, curte-circuita; se retornar False ou lançar exceção, tentamos o fallback
    de parsing para manter compatibilidade com dados legados.
    """
    if not tenant or not module_name:
        return False

    # 1. API Canônica (preferencial), mas não aborta fallback em caso de False
    if hasattr(tenant, "is_module_enabled"):
        try:
            canonical = bool(tenant.is_module_enabled(module_name))
            if canonical:
                return True
        except (AttributeError, TypeError, ValueError):
            logger.warning(
                "Erro ao chamar tenant.is_module_enabled para o tenant %s e módulo %s.",
                getattr(tenant, "id", None),
                module_name,
                exc_info=True,
            )

    # 2. Fallback para o campo 'enabled_modules'
    raw_modules = getattr(tenant, "enabled_modules", None)
    if raw_modules:
        enabled_list = _parse_enabled_modules(raw_modules)
        return module_name in enabled_list

    return False


def _check_superuser(user: AbstractBaseUser | AnonymousUser | None) -> AccessDecision | None:
    """Verifica se o usuário é superuser."""
    if getattr(user, "is_superuser", False):
        return AccessDecision(allowed=True, reason=REASON_SUPERUSER)
    return None


def _check_portal_user_policy(
    user: AbstractBaseUser | AnonymousUser,
    module_name: str,
) -> AccessDecision | None:
    """Aplica a política de acesso para usuários do portal."""
    if is_portal_user(user):
        portal_whitelist = getattr(settings, "PORTAL_ALLOWED_MODULES", [])
        if module_name not in portal_whitelist:
            return AccessDecision(allowed=False, reason=REASON_PORTAL_DENY)
        # Se está na whitelist e o módulo está habilitado (verificado antes), concede acesso.
        return AccessDecision(allowed=True, reason=REASON_OK)
    return None


def _check_permission_resolver(
    user: AbstractBaseUser | AnonymousUser,
    tenant: Tenant,
    module_name: str,
) -> AccessDecision | None:
    """Verifica a permissão usando o `permission_resolver`."""
    if not getattr(settings, "FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT", False):
        return None  # Se não for estrito, não interfere na decisão.

    try:
        resolver_mod = import_module("shared.services.permission_resolver")
        resolver = getattr(resolver_mod, "permission_resolver", None)
        if resolver:
            action_code = f"VIEW_{module_name.upper()}"
            try:
                allowed, _ = resolver.resolve(user, tenant, action_code)
            except Exception:
                logger.exception("Exceção no permission_resolver.resolve")
                return AccessDecision(allowed=False, reason=REASON_UNKNOWN_ERROR)
            if not allowed:
                return AccessDecision(allowed=False, reason=REASON_RESOLVER_DENY)
    except (ImportError, AttributeError):
        logger.exception("Falha ao executar o permission_resolver.")
        return AccessDecision(allowed=False, reason=REASON_UNKNOWN_ERROR)

    return None


def can_access_module(
    user: AbstractBaseUser | AnonymousUser | None,
    tenant: Tenant | None,
    module_name: str | None,
) -> AccessDecision:
    """Decide o acesso a um módulo, retornando sempre um AccessDecision."""
    # Inicia com uma decisão padrão de negação até que uma regra permita.
    decision = AccessDecision(allowed=False, reason=REASON_UNKNOWN_ERROR)

    # 1. Superuser tem acesso imediato.
    if (superuser_decision := _check_superuser(user)) is not None:
        return superuser_decision

    # 2. Validações de pré-requisitos.
    if not tenant:
        return AccessDecision(allowed=False, reason=REASON_NO_TENANT)
    if not module_name:
        return AccessDecision(allowed=False, reason=REASON_MODULE_NAME_EMPTY)
    if not _tenant_has_module(tenant, module_name):
        return AccessDecision(allowed=False, reason=REASON_MODULE_DISABLED)

    # 3. Se chegou aqui, a presunção é de acesso permitido, a menos que uma regra negue.
    decision = AccessDecision(allowed=True, reason=REASON_OK)

    # 4. Políticas específicas para usuários autenticados que podem negar o acesso.
    if user and user.is_authenticated:
        # A política do portal é uma exceção: ela concede se estiver na whitelist.
        if (portal_decision := _check_portal_user_policy(user, module_name)) is not None:
            return portal_decision  # Retorna a decisão do portal diretamente.

        # O resolvedor de permissões pode negar o acesso.
        if (resolver_decision := _check_permission_resolver(user, tenant, module_name)) is not None:
            decision = resolver_decision

    return decision


def explain_decision(decision: AccessDecision) -> str:
    """Retorna uma string descritiva simples da decisão."""
    return decision.reason


def _log_prometheus_metric(module_name: str | None, reason: str) -> None:
    """Incrementa o contador do Prometheus se habilitado."""
    if MODULE_DENY_COUNTER:
        with contextlib.suppress(Exception):
            MODULE_DENY_COUNTER.labels(module=module_name or "unknown", reason=reason).inc()


def _log_cache_metric(module_name: str | None, reason: str) -> None:
    """Incrementa um contador no cache para análise."""
    metric_key = f"module_deny_count:{module_name or 'unknown'}:{reason}"
    try:
        # Tenta usar um incremento atômico se disponível
        cu = import_module("shared.cache_utils")
        incr_atomic = cu.incr_atomic
        incr_atomic(metric_key, ttl=86400)
    except (ImportError, AttributeError):
        # Fallback para um get/set simples
        try:
            current_value = cache.get(metric_key, 0)
            cache.set(metric_key, int(current_value) + 1, timeout=86400)
        except (ValueError, TypeError):
            logger.warning("Falha ao incrementar métrica de negação no cache para %s.", metric_key)


def _create_audit_log_entry(
    user: AbstractBaseUser | AnonymousUser | None,
    tenant: Tenant | None,
    module_name: str | None,
    reason: str,
    request: HttpRequest | None,
) -> None:
    """Cria a entrada no AuditLog."""
    try:
        utils_mod = import_module("core.utils")
        models_mod = import_module("core.models")

        get_client_ip = utils_mod.get_client_ip
        audit_log_model = models_mod.AuditLog
        tenant_model = models_mod.Tenant

        ip_address = get_client_ip(request) if request else None
        user_ref = user if getattr(user, "is_authenticated", False) else None

        tenant_id = getattr(tenant, "id", None)
        change_msg = f"[MODULE_DENY] module={module_name or ''} reason={reason} tenant={tenant_id}"

        # Garantir que o campo FK 'tenant' receba uma instância válida ou None
        tenant_fk = tenant if isinstance(tenant, tenant_model) else None

        audit_log_model.objects.create(
            user=user_ref,
            tenant=tenant_fk,
            action_type="OTHER",
            ip_address=ip_address,
            change_message=change_msg,
        )
    except (ImportError, AttributeError):
        logger.exception("Falha crítica ao tentar criar o registro de log de auditoria.")


def log_module_denial(
    user: AbstractBaseUser | AnonymousUser | None,
    tenant: Tenant | None,
    module_name: str | None,
    reason: str,
    request: HttpRequest | None = None,
) -> None:
    """Registra uma negação de acesso a módulo de forma segura e multifacetada."""
    if not getattr(settings, "FEATURE_LOG_MODULE_DENIALS", True):
        return

    # Lógica de deduplicação para evitar spam de logs
    dedup_seconds = int(getattr(settings, "LOG_MODULE_DENY_DEDUP_SECONDS", DEFAULT_DEDUP_SECONDS))
    if dedup_seconds > 0 and module_name and user:
        cache_key = f"moddeny:{getattr(user, 'id', 0)}:{getattr(tenant, 'id', 0)}:{module_name}:{reason}"
        if cache.get(cache_key):
            return  # Se a chave existe, o log recente já foi feito.
        # Seta a chave de deduplicação imediatamente
        with contextlib.suppress(Exception):
            cache.set(cache_key, 1, timeout=dedup_seconds)

    # Registra as métricas
    _log_prometheus_metric(module_name, reason)
    _log_cache_metric(module_name, reason)

    # Cria o log de auditoria detalhado
    _create_audit_log_entry(user, tenant, module_name, reason, request)

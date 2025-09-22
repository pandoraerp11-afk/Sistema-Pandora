"""Camada central de autorização modular.

IMPORTANTE: Não remover funções legadas antes de validar usos.
Esta camada será usada gradualmente (feature flag) pelo menu e middleware.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

"""Import do permission_resolver removido para permitir monkeypatch dinâmico em testes.
A resolução agora ocorre dentro de can_access_module via importlib para refletir alterações
feitas com monkeypatch.setattr no módulo original (ex: test_authorization_logging).
"""
from importlib import import_module

from django.core.cache import cache

try:
    from prometheus_client import Counter as _PromCounter  # opcional

    _PROM_ENABLED = True
except Exception:  # pragma: no cover
    _PromCounter = None
    _PROM_ENABLED = False

if _PROM_ENABLED:
    MODULE_DENY_COUNTER = _PromCounter(
        "pandora_module_denials_total", "Total de negações de acesso a módulos", ["module", "reason"]
    )
else:  # pragma: no cover
    MODULE_DENY_COUNTER = None
import contextlib
import json

# Razões padronizadas (strings simples para facilitar logging e cabeçalhos)
REASON_OK = "OK"
REASON_NO_TENANT = "NO_TENANT"
REASON_SUPERUSER = "SUPERUSER_BYPASS"
REASON_MODULE_NAME_EMPTY = "MODULE_NAME_EMPTY"
REASON_MODULE_DISABLED = "MODULE_DISABLED_FOR_TENANT"
REASON_PORTAL_DENY = "PORTAL_NOT_IN_WHITELIST"
REASON_UNKNOWN_ERROR = "UNKNOWN_ERROR"
REASON_RESOLVER_DENY = "PERMISSION_RESOLVER_DENY"

PORTAL_USER_GROUP_NAME = getattr(settings, "PORTAL_USER_GROUP_NAME", "PortalUser")


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str = REASON_OK


def is_portal_user(user) -> bool:
    """Heurística NÃO invasiva para identificar usuário portal sem exigir migração imediata.
    Ordem de verificação:
    1. Campo user_type == 'PORTAL'
    2. Atributo dinâmico is_portal_user True
    3. Grupo Django 'PortalUser'
    (Extensível futuramente)
    """
    if not user or isinstance(user, AnonymousUser):
        return False
    # Campo canônico
    if getattr(user, "user_type", None) == "PORTAL":
        return True
    if getattr(user, "is_portal_user", False):  # atributo ad hoc
        return True
    try:
        return user.groups.filter(name=PORTAL_USER_GROUP_NAME).exists()
    except Exception:
        return False


def _tenant_has_module(tenant, module_name: str) -> bool:
    try:
        if not (tenant and module_name):
            return False
        # Primeiro usar API canonical
        if hasattr(tenant, "is_module_enabled"):
            try:
                if tenant.is_module_enabled(module_name):
                    return True
            except Exception:
                pass
        # Fallback: aceitar enabled_modules como JSON string de lista ou lista literal
        raw = getattr(tenant, "enabled_modules", None)
        if not raw:
            return False
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except Exception:
                # Pode estar em formato já de lista textual simples, tentar heurística básica
                parsed = []
            if isinstance(parsed, list):
                return module_name in parsed
        elif isinstance(raw, list):
            return module_name in raw
        elif isinstance(raw, dict):  # já tratado em is_module_enabled normalmente
            mods = raw.get("modules") if "modules" in raw else None
            if isinstance(mods, list):
                return module_name in mods
        return False
    except Exception:
        return False


def can_access_module(user, tenant, module_name: str | None) -> AccessDecision:
    """Decide acesso a um módulo.

    NÃO levanta exceções; sempre retorna AccessDecision.
    Mantém compatibilidade: se feature flag estiver desligada, chamada pode ser evitada pelo caller.
    """
    # Superuser
    try:
        if getattr(user, "is_superuser", False):
            return AccessDecision(True, REASON_SUPERUSER)
    except Exception:
        pass

    if not tenant:
        # Sem tenant (usuário portal puro?) não liberamos menu corporativo
        return AccessDecision(False, REASON_NO_TENANT)

    if not module_name:
        return AccessDecision(False, REASON_MODULE_NAME_EMPTY)

    # Checar módulo habilitado para o tenant
    if not _tenant_has_module(tenant, module_name):
        return AccessDecision(False, REASON_MODULE_DISABLED)

    # Política portal (whitelist tem precedência positiva: se estiver na whitelist, libera e não aplica resolver estrito)
    if is_portal_user(user):
        portal_whitelist = getattr(settings, "PORTAL_ALLOWED_MODULES", [])
        if module_name not in portal_whitelist:
            return AccessDecision(False, REASON_PORTAL_DENY)
        # Se está na whitelist e módulo habilitado, acesso concedido imediatamente
        return AccessDecision(True, REASON_OK)

    # Integração básica com permission_resolver: ação VIEW_<MODULE>
    try:
        action_code = f"VIEW_{module_name.upper()}"
        # Import dinâmico para refletir monkeypatch em runtime
        try:
            resolver_mod = import_module("shared.services.permission_resolver")
            resolver = getattr(resolver_mod, "permission_resolver", None)
        except Exception:  # pragma: no cover
            resolver = None
        if resolver:
            allowed_action, reason_detail = resolver.resolve(user, tenant, action_code)
            if not allowed_action:
                if getattr(settings, "FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT", False):
                    return AccessDecision(False, REASON_RESOLVER_DENY)
        # Se não houver resolver ou erro, comportamento permissivo (desde que módulo habilitado) a menos que estrito exija negação em erro
    except Exception:
        if getattr(settings, "FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT", False):
            return AccessDecision(False, REASON_UNKNOWN_ERROR)

    # FUTURO: Roles / object-level permissions aqui

    return AccessDecision(True, REASON_OK)


def explain_decision(decision: AccessDecision) -> str:
    """Retorna string descritiva simples (pode ser expandida para mapear reasons)."""
    return decision.reason


def log_module_denial(user, tenant, module_name: str | None, reason: str, request=None) -> None:
    """Registra uma negação de acesso a módulo em AuditLog de forma tolerante a erros.

    - Não levanta exceções (fail-safe) para não quebrar fluxo de request.
    - Usa action_type OTHER para evitar necessidade de migration.
    - Mensagem estruturada iniciando com [MODULE_DENY] para facilitar grep / consulta.
    - Controlado por feature flag opcional FEATURE_LOG_MODULE_DENIALS (default True).
    """
    if not getattr(settings, "FEATURE_LOG_MODULE_DENIALS", True):  # flag opcional
        return
    try:  # Import dentro da função para evitar import circular em inicialização
        # Deduplicação temporal opcional (evita spam de logs em múltiplos reloads rápidos)
        try:
            from django.conf import settings as _s

            dedup_seconds = int(getattr(_s, "LOG_MODULE_DENY_DEDUP_SECONDS", 0) or 0)
        except Exception:
            dedup_seconds = 0
        if dedup_seconds and module_name:
            cache_key = f"moddeny:{getattr(user, 'id', 0)}:{getattr(tenant, 'id', 0)}:{module_name}:{reason}"
            # Se chave existe podemos ter dois cenários:
            # 1. Log realmente já foi criado (situação normal) -> retornar cedo.
            # 2. Chave "stale" deixada em cache (ex: entre testes pytest o DB é limpo mas cache persiste)
            #    Nesse caso precisamos recriar o log (não retornar). Para detectar, consultamos o banco.
            existing_flag = cache.get(cache_key)
            if existing_flag:
                try:
                    from .models import AuditLog  # import local para evitar circular

                    # Busca minimalista: mesmo user/tenant/action_type OTHER + módulo na mensagem
                    if AuditLog.objects.filter(
                        user=user if getattr(user, "is_authenticated", False) else None,
                        tenant=tenant,
                        action_type="OTHER",
                        change_message__startswith="[MODULE_DENY]",
                        change_message__contains=f"module={module_name or ''}",
                    ).exists():
                        return  # log válido já existe
                    # Caso contrário, tratamos como stale e prosseguimos para criar novo log.
                except Exception:
                    # Qualquer erro na verificação: manter comportamento anterior (retornar cedo)
                    return
        # Métrica simples (contador diário por módulo + reason)
        try:
            # Incremento tolerante: usa utilitário com lock local para simular atomicidade em backends simples
            from shared.cache_utils import incr_atomic  # import local p/ evitar custo global se não usado

            metric_key = f"module_deny_count:{module_name or 'unknown'}:{reason}"
            incr_atomic(metric_key, ttl=86400)
        except Exception:
            # Fallback extremamente simples
            try:
                metric_key = f"module_deny_count:{module_name or 'unknown'}:{reason}"
                cur = cache.get(metric_key, 0)
                cache.set(metric_key, cur + 1, timeout=86400)
            except Exception:
                pass
        from .models import AuditLog  # type: ignore
        from .utils import get_client_ip  # type: ignore

        ip = get_client_ip(request) if request else None
        user_ref = user if getattr(user, "is_authenticated", False) else None
        AuditLog.objects.create(
            user=user_ref,
            tenant=tenant,
            action_type="OTHER",
            ip_address=ip,
            change_message=f"[MODULE_DENY] module={module_name or ''} reason={reason} tenant={getattr(tenant, 'id', None)}",
        )
        # Prometheus counter
        if MODULE_DENY_COUNTER:
            try:
                MODULE_DENY_COUNTER.labels(module=module_name or "unknown", reason=reason).inc()
            except Exception:  # pragma: no cover
                pass
        # Seta chave de deduplicação somente após criação bem-sucedida
        if dedup_seconds and module_name:
            with contextlib.suppress(Exception):
                cache.set(cache_key, 1, timeout=dedup_seconds)
    except Exception:
        # Silencia qualquer erro de logging para não impactar request principal
        pass


__all__ = [
    "AccessDecision",
    "can_access_module",
    "explain_decision",
    "log_module_denial",
    "REASON_OK",
    "REASON_NO_TENANT",
    "REASON_SUPERUSER",
    "REASON_MODULE_NAME_EMPTY",
    "REASON_MODULE_DISABLED",
    "REASON_PORTAL_DENY",
    "REASON_UNKNOWN_ERROR",
    "REASON_RESOLVER_DENY",
]

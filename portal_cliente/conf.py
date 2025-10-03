"""Config utilitário para Portal Cliente (leitura segura de settings).

Fornece funções para obter valores com fallback sem acoplamento direto
às defaults embutidas nas views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

if TYPE_CHECKING:  # pragma: no cover
    from core.models import Tenant

    from .models import PortalClienteConfiguracao


def _tenant_cfg(tenant: Tenant | None) -> PortalClienteConfiguracao | None:
    if tenant is None:
        return None
    try:  # pragma: no cover - acesso simples
        return tenant.portal_config  # attr definido via related_name
    except (ObjectDoesNotExist, AttributeError):
        return None


def get_cache_ttl() -> int:
    """TTL (segundos) para cache de listagens/ETag."""
    return int(getattr(settings, "PORTAL_CLIENTE_CACHE_TTL", 60))


def get_slots_throttle_limit() -> int:
    """Limite de requisições/min para slots."""
    return int(getattr(settings, "PORTAL_CLIENTE_SLOTS_THROTTLE", 20))


def get_listas_throttle_limit() -> int:
    """Limite de requisições/min para listagens (serviços, profissionais)."""
    return int(getattr(settings, "PORTAL_CLIENTE_LISTAS_THROTTLE", 30))


def get_cancelamento_limite_horas(tenant: Tenant | None = None) -> int:
    """Horas mínimas de antecedência exigidas para cancelamento."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.cancelamento_limite_horas)
    return int(getattr(settings, "PORTAL_CLIENTE_CANCELAMENTO_LIMITE_HORAS", 24))


def get_checkin_antecedencia_minutos(tenant: Tenant | None = None) -> int:
    """Minutos antes do horário permitido para check-in (default 30)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.checkin_antecedencia_min)
    return int(getattr(settings, "PORTAL_CLIENTE_CHECKIN_ANTECEDENCIA_MIN", 30))


def get_finalizacao_tolerancia_horas(tenant: Tenant | None = None) -> int:
    """Horas após horário de início em que finalização ainda é aceita (default 6)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.finalizacao_tolerancia_horas)
    return int(getattr(settings, "PORTAL_CLIENTE_FINALIZACAO_TOLERANCIA_H", 6))


def get_checkin_tolerancia_pos_minutos(tenant: Tenant | None = None) -> int:
    """Minutos após o horário de início em que ainda se aceita check-in (default 60)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.checkin_tolerancia_pos_min)
    return int(getattr(settings, "PORTAL_CLIENTE_CHECKIN_TOLERANCIA_POS_MIN", 60))


# --- Limites de throttling para endpoints de ação (parametrizáveis) --- #


def get_throttle_checkin_limit(tenant: Tenant | None = None) -> int:
    """Limite de tentativas de check-in por janela (default 12)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.throttle_checkin)
    return int(getattr(settings, "PORTAL_CLIENTE_THROTTLE_CHECKIN", 12))


def get_throttle_finalizar_limit(tenant: Tenant | None = None) -> int:
    """Limite de finalizações por janela (default 10)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.throttle_finalizar)
    return int(getattr(settings, "PORTAL_CLIENTE_THROTTLE_FINALIZAR", 10))


def get_throttle_avaliar_limit(tenant: Tenant | None = None) -> int:
    """Limite de avaliações por janela (default 10)."""
    cfg = _tenant_cfg(tenant)
    if cfg:
        return int(cfg.throttle_avaliar)
    return int(getattr(settings, "PORTAL_CLIENTE_THROTTLE_AVALIAR", 10))

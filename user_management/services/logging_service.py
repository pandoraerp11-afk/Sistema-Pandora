"""Serviço de logging unificado de atividades de usuário.

Verificado inexistência de equivalente centralizado: termos pesquisados: LogAtividadeUsuario.objects.create, log_activity, logging_service.
Objetivo: substituir criações diretas de LogAtividadeUsuario espalhadas por signals e views.

Contrato:
log_activity(user, acao, modulo, descricao:str, objeto=None, ip=None, user_agent=None, extra:dict|None=None)
 - user: User obrigatório
 - acao: string curta (ex: LOGIN, LOGOUT, UPDATE_PROFILE)
 - modulo: domínio funcional (ex: USER_MGMT, AUTH, PERFIL)
 - descricao: mensagem livre indexável
 - objeto: model instance opcional; se fornecido salva content_type e object_id
 - ip: se não fornecido tenta extrair de request.META
 - user_agent: idem
 - extra: dict serializado em campo texto (JSON) futuro (placeholder)

Futuro: mover para app core.audit e integrar com pipeline de auditoria externa.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.utils import timezone

from ..models import LogAtividadeUsuario

try:
    import json
except ImportError:  # pragma: no cover
    json = None


def _serialize_extra(extra):
    if not extra:
        return None
    if json:
        try:
            return json.dumps(extra, ensure_ascii=False)[:1000]
        except Exception:  # pragma: no cover
            return str(extra)[:1000]
    return str(extra)[:1000]


def log_activity(
    user,
    acao: str,
    modulo: str,
    descricao: str,
    objeto=None,
    ip: str | None = None,
    user_agent: str | None = None,
    extra: dict | None = None,
):
    """Registra uma atividade de usuário de forma resiliente.

    Ajustes de robustez:
      - Se IP não for fornecido ou vier vazio, usa '0.0.0.0' (evita IntegrityError em GenericIPAddressField).
      - Se user_agent não vier, define 'N/A'.
      - Corta tamanhos para evitar exceções de comprimento.
      - Silencia falhas (p/ não quebrar fluxo crítico como login/unlock) mas poderia futuramente enfileirar.
    """
    if not user:  # Sem usuário não registra
        return
    safe_ip = ip if ip else "0.0.0.0"
    # GenericIPAddressField aceita IPv4/IPv6 – '0.0.0.0' é válido universal.
    safe_ua = (user_agent or "N/A")[:255]
    try:
        LogAtividadeUsuario.objects.create(
            user=user,
            acao=(acao or "")[:100],
            modulo=(modulo or "")[:50],
            descricao=(descricao or "")[:255],
            ip_address=safe_ip,
            user_agent=safe_ua,
            extra_json=_serialize_extra(extra),
        )
    except Exception:  # pragma: no cover - não queremos derrubar fluxo
        pass


def log_activity_many(entries: Iterable[dict]):
    """Registra múltiplas atividades em lote. Cada entry: {user, acao, modulo, descricao, ip?, user_agent?, extra?}
    Falhas são ignoradas individualmente.
    """
    objs = []
    now = timezone.now()
    for e in entries:
        user = e.get("user")
        if not user:
            continue
        try:
            ip = e.get("ip") or "0.0.0.0"
            ua = (e.get("user_agent") or "N/A")[:255]
            objs.append(
                LogAtividadeUsuario(
                    user=user,
                    acao=(e.get("acao") or "")[:100],
                    modulo=(e.get("modulo") or "")[:50],
                    descricao=(e.get("descricao") or "")[:255],
                    ip_address=ip,
                    user_agent=ua,
                    extra_json=_serialize_extra(e.get("extra")),
                    timestamp=now,
                )
            )
        except Exception:  # pragma: no cover
            continue
    if objs:
        try:
            LogAtividadeUsuario.objects.bulk_create(objs, ignore_conflicts=True)
        except Exception:  # pragma: no cover
            pass

"""Sistema de resolução de permissões unificado.

Implementa hierarquia de precedência: Deny > Allow > Role > Papel > Default.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import time
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils import timezone

User = get_user_model()

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models.query import QuerySet

    from user_management.models import PermissaoPersonalizada as PermissaoPersonalizadaModel

    PermissaoPersonalizadaType = PermissaoPersonalizadaModel
else:
    PermissaoPersonalizadaType = Any  # type: ignore[assignment]

TenantType = Any
UserType = Any
P = ParamSpec("P")
R = TypeVar("R")


logger = logging.getLogger(__name__)


class PermissionSource(str, Enum):  # str para compatibilidade
    """Enum de fontes de decisão de permissão.

    Mantém compatibilidade: testes existentes comparam literais strings.
    """

    PERSONALIZADA = "personalizada"
    ROLE = "role"
    DEFAULT = "default"
    PUBLIC = "public"
    ACCOUNT_BLOCK = "account_block"
    INVALID_USER = "invalid_user"
    ANONYMOUS_USER = "anonymous_user"
    INACTIVE_USER = "inactive_user"
    NO_TENANT = "no_tenant"
    CACHE = "cache"
    IMPLICIT = "implicit"
    EXCEPTION = "exception"


# Constantes
ACTION_MAP_CACHE_TTL_SECONDS = 300
HASH_CACHE_TTL_SECONDS = 60

_METRICS_ENABLED = False  # Métricas desativadas temporariamente para simplificar correção de tipos


@dataclasses.dataclass
class PermissionArguments:
    """Agrupa os argumentos para a verificação de permissão."""

    user: UserType
    tenant: TenantType
    action: str
    resource: Any | None = None
    trace: list[str] = dataclasses.field(default_factory=list)
    trace_enabled: bool = False


@dataclasses.dataclass
class PermissionResult:
    """Representa o resultado de uma decisão de permissão."""

    allowed: bool
    source: PermissionSource | str
    reason: str


@dataclasses.dataclass
class PermissionDecision:
    """Compat: decisão detalhada usada pelos testes legados."""

    allowed: bool
    reason: str
    trace: str | None = None
    source: str | None = None


class PermissionResolver:
    """Resolve permissões com base em uma hierarquia de precedência."""

    def __init__(self) -> None:
        """Inicializa o resolver."""
        # TTL padrão do cache (compat com versão anterior)
        self.CACHE_TTL: int = getattr(settings, "PERMISSION_CACHE_TTL", 300)

        # Cache do action map (baseado em settings)
        self._action_map_cache: dict[str, list[str]] = {}
        self._action_map_cache_ts: float = 0.0

        # Era global para invalidação total sem apagar chaves
        self.cache_prefix = "perm_resolver"
        self._global_era_key = f"{self.cache_prefix}:global_era"
        try:
            if cache.get(self._global_era_key) is None:
                cache.add(self._global_era_key, 1, self.CACHE_TTL)
        except Exception as exc:  # noqa: BLE001 - backends sem add
            logger.debug("Falha ao inicializar era global: %s", exc)

        # Hash do action map (para compor chave de cache de forma determinística)
        self._action_map_hash_cache: str | None = None
        self._action_map_hash_ts: float = 0.0
        # Métricas
        # Placeholders de métricas (desligadas). Reintroduzir posteriormente de forma tipada.
        self._m_decisions = None
        self._m_cache_hits = None
        self._m_cache_misses = None
        self._m_latency = None
        self._m_cache_ttl = None

        # Último trace coletado (compat com resolve_decision)
        self._last_trace_lines: list[str] = []
        # Pipeline compatível por padrão
        self.pipeline: list[str] = ["_step_role", "_step_implicit", "_step_default"]

    # ------------------------------------------------------------------
    # API pública auxiliar
    def get_last_trace_lines(self) -> list[str]:
        """Retorna cópia imutável do último trace coletado.

        Fornece acesso seguro para testes e diagnósticos sem expor o
        atributo interno `_last_trace_lines` diretamente, evitando dependência
        frágil de nome interno.
        """
        return list(self._last_trace_lines)

    # ------------------------------------------------------------------
    # Debug / introspecção
    def debug_personalized(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: Any | None = None,  # noqa: ANN401
    ) -> list[dict[str, Any]]:
        """Retorna lista detalhada das permissões personalizadas candidatas.

        Cada item contém:
        - id: ID da regra (se houver)
        - concedida: bool
        - score: score calculado (ou None se descartada)
        - aplicado: True se regra permanece após filtro
        - motivo_exclusao: razão textual caso descartada
        - scope_tenant_id / recurso: escopos para inspeção rápida

        Não utiliza cache. Apenas leitura direta.
        """
        results: list[dict[str, Any]] = []
        try:
            tenant_id = getattr(tenant, "id", None)
            qs = self._build_custom_permission_query(user, action)
            perms = list(qs)
        except Exception as exc:  # noqa: BLE001
            logger.debug("debug_personalized falhou ao obter query: %s", exc)
            return []

        now = timezone.now()
        for p in perms:
            motivo_exclusao = None
            try:
                # Tratar expiração explicitamente
                data_exp = getattr(p, "data_expiracao", None)
                if data_exp and data_exp < now:
                    motivo_exclusao = "expirada"
                    applied = False
                    final_score = None
                else:
                    score = self._calculate_permission_score(p, resource, tenant_id)
                    if score < 0:
                        motivo_exclusao = "score_negativo"
                        applied = False
                        final_score = None
                    else:
                        applied = True
                        final_score = score
            except Exception as exc:  # noqa: BLE001
                motivo_exclusao = f"erro_score:{exc}"
                applied = False
                final_score = None
            results.append(
                {
                    "id": getattr(p, "id", None),
                    "concedida": getattr(p, "concedida", None),
                    "score": final_score,
                    "aplicado": applied,
                    "motivo_exclusao": motivo_exclusao,
                    "scope_tenant_id": getattr(p, "scope_tenant_id", None),
                    "recurso": getattr(p, "recurso", None),
                },
            )
        # Ordenar applied primeiro por score desc para refletir ordenação usada na decisão
        results.sort(key=lambda r: (-1 if r["score"] is None else r["score"]), reverse=True)
        return results

    def _get_version(self, user_id: int, tenant_id: int) -> int:
        """Obtém versão de cache específica user/tenant."""
        version_key = f"{self.cache_prefix}:ver:{user_id}:{tenant_id}"
        version = cache.get(version_key)
        if version is None:
            version = 1
            cache.set(version_key, version, self.CACHE_TTL)
        return version

    def _get_global_era(self) -> int:
        try:
            era = cache.get(self._global_era_key)
            if era is None:
                era = 1
                cache.set(self._global_era_key, era, self.CACHE_TTL)
            return int(era)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao obter era global: %s", exc)
            return 1

    def _bump_global_era(self) -> None:
        try:
            era = self._get_global_era()
            cache.set(self._global_era_key, era + 1, self.CACHE_TTL)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao incrementar era global: %s", exc)

    def _get_cache_key(self, *fargs: Any, **fkwargs: Any) -> str:  # noqa: ANN401
        """Compat: aceita tanto (PermissionArguments, mode='has') quanto.

        (user_id, tenant_id, action, resource=None, mode='has').

        Retorna chave de cache única considerando era, versão e hash do action map.
        """
        mode = fkwargs.get("mode", "has")
        if fargs and isinstance(fargs[0], PermissionArguments):
            args = fargs[0]
            user_id = getattr(args.user, "id", 0)
            tenant_id = getattr(args.tenant, "id", 0)
            action = args.action
            resource_key = args.resource if args.resource else "global"
            amap_hash = self._get_action_map_hash(args.tenant)
            version = self._get_version(user_id, tenant_id)
            era = self._get_global_era()
            # Caminho moderno pode incluir 'mode' para diferenciar chaves
            return (
                f"{self.cache_prefix}:{mode}:{era}:{amap_hash}:{version}:{user_id}:{tenant_id}:{action}:{resource_key}"
            )
        # Forma legada: user_id, tenant_id, action[, resource]
        idx_user, idx_tenant, idx_action, idx_resource = 0, 1, 2, 3
        user_id = int(fargs[idx_user]) if len(fargs) > idx_user else 0
        tenant_id = int(fargs[idx_tenant]) if len(fargs) > idx_tenant else 0
        action = str(fargs[idx_action]) if len(fargs) > idx_action else ""
        resource_key = (
            fargs[idx_resource] if len(fargs) > idx_resource and fargs[idx_resource] is not None else "global"
        )
        amap_hash = self._get_action_map_hash(None)
        version = self._get_version(user_id, tenant_id)
        era = self._get_global_era()
        # Compat: NÃO incluir 'mode' na chave legada (testes dependem do split)
        return f"{self.cache_prefix}:{era}:{amap_hash}:{version}:{user_id}:{tenant_id}:{action}:{resource_key}"

    # ---------- Action map (compatível com versão antiga) ----------
    def _get_action_map_hash(self, tenant: TenantType) -> str:
        now = time.time()
        if self._action_map_hash_cache and (now - self._action_map_hash_ts) < HASH_CACHE_TTL_SECONDS:
            return self._action_map_hash_cache
        amap = self._get_action_map(tenant)
        items = sorted((k, tuple(sorted(v))) for k, v in amap.items())
        raw = repr(items).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()[:8]
        self._action_map_hash_cache = h
        self._action_map_hash_ts = now
        return h

    def _merge_action_maps(
        self,
        base: dict[str, list[str]],
        extra: dict[str, list[str]] | None,
    ) -> dict[str, list[str]]:
        if not extra:
            return base
        for action, tokens in extra.items():
            if action in base:
                for t in tokens:
                    if t not in base[action]:
                        base[action].append(t)
            else:
                base[action] = list(tokens)
        return base

    def _get_action_map(self, _tenant: TenantType | None = None) -> dict[str, list[str]]:
        """Mapa base de actions -> tokens com suporte a extensões via settings.

        Parâmetro tenant é aceito por compatibilidade; pode ser ignorado.
        """
        base: dict[str, list[str]] = {
            "CREATE_COTACAO": ["can_create_cotacao", "is_admin"],
            "VIEW_COTACAO": ["can_view_cotacao", "can_create_cotacao", "is_admin"],
            "SUBMIT_PROPOSTA": ["can_submit_proposta"],
            "VIEW_PROPOSTA": ["can_view_proposta", "can_submit_proposta"],
            "SELECT_PROPOSTA": ["can_select_proposta", "is_admin"],
            "VIEW_DASHBOARD_FORNECEDOR": ["can_access_fornecedor_portal"],
            # CRUD FORNECEDOR (provisório)
            "VIEW_FORNECEDOR": ["can_view_fornecedor", "is_admin"],
            "CREATE_FORNECEDOR": ["can_add_fornecedor", "is_admin"],
            "EDIT_FORNECEDOR": ["can_change_fornecedor", "is_admin"],
            "DELETE_FORNECEDOR": ["can_delete_fornecedor", "is_admin"],
            # CRUD FUNCIONARIO (provisório)
            "VIEW_FUNCIONARIO": ["can_view_funcionario", "is_admin"],
            "CREATE_FUNCIONARIO": ["can_add_funcionario", "is_admin"],
            "EDIT_FUNCIONARIO": ["can_change_funcionario", "is_admin"],
            "DELETE_FUNCIONARIO": ["can_delete_funcionario", "is_admin"],
            # CRUD PRODUTO
            "VIEW_PRODUTO": ["can_view_produto", "is_admin"],
            "CREATE_PRODUTO": ["can_add_produto", "is_admin"],
            "EDIT_PRODUTO": ["can_change_produto", "is_admin"],
            "DELETE_PRODUTO": ["can_delete_produto", "is_admin"],
            # CRUD SERVICO
            "VIEW_SERVICO": ["can_view_servico", "is_admin"],
            "CREATE_SERVICO": ["can_add_servico", "is_admin"],
            "EDIT_SERVICO": ["can_change_servico", "is_admin"],
            "DELETE_SERVICO": ["can_delete_servico", "is_admin"],
        }
        extra = getattr(settings, "PERMISSION_ACTION_MAP_EXTRA", None)
        if isinstance(extra, dict):
            base = self._merge_action_maps(base, extra)
        provider_path = getattr(settings, "PERMISSION_ACTION_MAP_PROVIDER", None)
        if provider_path:
            try:
                mod_name, func_name = provider_path.rsplit(".", 1)
                provider = getattr(__import__(mod_name, fromlist=[func_name]), func_name)
                provided = provider() or {}
                if isinstance(provided, dict):
                    base = self._merge_action_maps(base, provided)
            except Exception as e:  # noqa: BLE001
                logger.warning("Falha ao carregar provider de action map '%s': %s", provider_path, e)
        return base

    def _validate_initial_state(self, args: PermissionArguments) -> PermissionResult | None:
        """Valida o estado inicial do usuário e do tenant."""
        if not hasattr(args.user, "is_authenticated"):
            return PermissionResult(allowed=False, source=PermissionSource.INVALID_USER, reason="Usuário inválido")
        if args.user.is_anonymous:
            return PermissionResult(allowed=False, source=PermissionSource.ANONYMOUS_USER, reason="Usuário anônimo")
        if not args.user.is_active:
            return PermissionResult(allowed=False, source=PermissionSource.INACTIVE_USER, reason="Usuário inativo")
        if not args.tenant:
            return PermissionResult(allowed=False, source=PermissionSource.NO_TENANT, reason="Tenant não fornecido")
        return None

    def has_permission(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: Any | None = None,  # noqa: ANN401
        *,
        _force_trace: bool = False,
    ) -> bool:
        """Verifica se um usuário tem uma permissão específica."""
        t_start = time.perf_counter() if _METRICS_ENABLED else 0.0
        trace_enabled = _force_trace or getattr(settings, "PERMISSION_RESOLVER_TRACE", False)
        args = PermissionArguments(
            user=user,
            tenant=tenant,
            action=action,
            resource=resource,
            trace_enabled=trace_enabled,
        )

        # 1. Validação inicial
        if (validation_result := self._validate_initial_state(args)) is not None:
            if args.trace_enabled:
                args.trace.append(f"Initial validation failed: {validation_result.reason}")
            return validation_result.allowed

        # 2. Verificação do cache
        cache_key = self._get_cache_key(args, mode="has")
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self._record_cache_hit(t_start, cache_key)
            # Compat: se trace estiver ativo, registrar cache_hit
            if trace_enabled:
                self._last_trace_lines = [f"cache_hit: key={cache_key}"]
            return bool(cached_result)

        if self._m_cache_misses:
            self._m_cache_misses.inc()

        # 3. Resolução de permissão (lógica principal)
        result = self._resolve_permission_logic(args)

        # 4. Armazenamento em cache e finalização
        cache.set(cache_key, result.allowed, timeout=self.CACHE_TTL)
        self._finalize_and_log(args, result, t_start)
        return result.allowed

    def explain_permission(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: Any | None = None,  # noqa: ANN401
        *,
        _force_trace: bool = False,
    ) -> PermissionResult:
        """Verifica uma permissão e retorna um objeto de decisão detalhado."""
        t_start = time.perf_counter() if _METRICS_ENABLED else 0.0
        trace_enabled = _force_trace or getattr(settings, "PERMISSION_RESOLVER_TRACE", False)
        args = PermissionArguments(
            user=user,
            tenant=tenant,
            action=action,
            resource=resource,
            trace_enabled=trace_enabled,
        )

        # 1. Validação inicial
        if (validation_result := self._validate_initial_state(args)) is not None:
            if args.trace_enabled:
                args.trace.append(f"Initial validation failed: {validation_result.reason}")
            return validation_result

        # 2. Verificação do cache
        cache_key = self._get_cache_key(args, mode="has")
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self._record_cache_hit(t_start, cache_key)
            return self._build_cached_permission_result(args, cache_key, cached_result)

        if self._m_cache_misses:
            self._m_cache_misses.inc()

        # 3. Resolução de permissão (lógica principal)
        result = self._resolve_permission_logic(args)
        self._append_trace_markers(args, result)

        # 4. Armazenamento em cache e finalização
        cache.set(cache_key, result.allowed, timeout=self.CACHE_TTL)
        self._finalize_and_log(args, result, t_start)
        return result

    def _record_cache_hit(self, t_start: float, cache_key: str) -> None:
        """Registra métricas para um acerto de cache."""
        if not _METRICS_ENABLED:
            return
        if self._m_cache_hits:
            self._m_cache_hits.inc()
        if self._m_latency and t_start > 0:
            self._m_latency.observe(time.perf_counter() - t_start)
        if self._m_cache_ttl:
            ttl = cache.ttl(cache_key)
            if ttl is not None:
                self._m_cache_ttl.observe(ttl)

    def _finalize_and_log(self, args: PermissionArguments, result: PermissionResult, t_start: float) -> None:
        """Finaliza a resolução, registrando logs e métricas."""
        if args.trace_enabled:
            dt = (time.perf_counter() - t_start) * 1000 if t_start > 0 else 0.0
            header = (
                f"PERMISSION TRACE: {args.user} -> {args.action} on {args.resource or 'global'} "
                f"-> {'ALLOWED' if result.allowed else 'DENIED'} "
                f"({result.source}: {result.reason}) [{dt:.2f}ms]"
            )
            logger.info("%s\n%s", header, "\n".join(f"  - {line}" for line in args.trace))

        if not _METRICS_ENABLED:
            return
        if self._m_decisions:
            self._m_decisions.labels(action=args.action, source=result.source, allowed=str(result.allowed)).inc()
        if self._m_latency and t_start > 0:
            self._m_latency.observe(time.perf_counter() - t_start)

    def _build_cached_permission_result(
        self,
        args: PermissionArguments,
        cache_key: str,
        cached_result: Any,  # noqa: ANN401
    ) -> PermissionResult:
        """Cria um PermissionResult a partir de um valor booleano armazenado em cache."""
        if args.trace_enabled:
            self._last_trace_lines = [f"cache_hit: key={cache_key}"]
        return PermissionResult(
            allowed=bool(cached_result),
            source=PermissionSource.CACHE,
            reason=f"cache_hit: key={cache_key}",
        )

    def _append_trace_markers(self, args: PermissionArguments, result: PermissionResult) -> None:
        """Anexa marcadores de trace compatíveis à lista de trace."""
        if not args.trace_enabled:
            return
        marker = None
        if result.source == "default":
            marker = "default_result"
        elif result.source == "role" and result.allowed:
            marker = "role_allow"
        elif result.source in {"custom", "personalizada"}:
            # Normalizar marcador esperado pelos testes (contém 'personalizada')
            marker = "personalizada"
        if marker:
            args.trace.append(marker)
        self._last_trace_lines = list(args.trace)

    def _resolve_permission_logic(self, args: PermissionArguments) -> PermissionResult:
        """Contém a lógica principal de resolução de permissões."""
        # 0. Ações públicas: permitem por padrão
        if args.action.endswith("_PUBLIC"):
            if args.trace_enabled:
                args.trace.append("public_default_allow")
            return PermissionResult(allowed=True, source=PermissionSource.PUBLIC, reason="Ação pública por padrão")

        # 1. Verificar bloqueios de conta
        if (res := self._check_account_blocks_args(args)) is not None:
            return res

        # 2. Verificar permissões personalizadas (Deny/Allow)
        if (res := self._check_custom_permissions(args)) is not None:
            return res

        # 2.5. Hook de roles implícitas (para testes/compat)
        if hasattr(self, "_check_implicit_roles_args"):
            try:
                hook_res = self._check_implicit_roles_args(args)
                if hook_res is not None:
                    return hook_res
            except Exception as exc:  # noqa: BLE001
                logger.debug("Hook _check_implicit_roles_args falhou: %s", exc)

        # 3. Verificar permissões baseadas em roles
        if (res := self._check_role_permissions(args)) is not None:
            return res

        # 4. Se nada retornou (pipeline exaurida) => negar por default explícito
        return PermissionResult(
            allowed=False,
            source=PermissionSource.DEFAULT,
            reason="Ação não permitida (default)",
        )

    def _check_account_blocks_args(self, args: PermissionArguments) -> PermissionResult | None:
        """Verifica bloqueios de conta/tenant para o caminho moderno (args)."""
        try:
            from core.models import TenantUser  # noqa: PLC0415

            TenantUser.objects.get(user=args.user, tenant=args.tenant)
        except Exception as exc:  # noqa: BLE001
            from core.models import TenantUser  # noqa: PLC0415

            if isinstance(exc, TenantUser.DoesNotExist):
                return PermissionResult(
                    allowed=False,
                    source=PermissionSource.ACCOUNT_BLOCK,
                    reason="Usuário não pertence ao tenant",
                )
            logger.debug("Falha ao buscar TenantUser: %s", exc)
            return PermissionResult(
                allowed=False,
                source=PermissionSource.ACCOUNT_BLOCK,
                reason="Erro ao validar TenantUser",
            )

        try:
            from portal_fornecedor.models import AcessoFornecedor  # noqa: PLC0415

            acesso = AcessoFornecedor.objects.get(usuario=args.user, fornecedor__tenant=args.tenant)
            if not acesso.pode_acessar_portal():
                return PermissionResult(
                    allowed=False,
                    source=PermissionSource.ACCOUNT_BLOCK,
                    reason="Acesso ao portal bloqueado",
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignorando checagem de portal fornecedor: %s", exc)
        return None

    def _check_account_blocks(self, *params: Any) -> PermissionResult | None | tuple[bool, str]:  # noqa: ANN401
        """Compat: aceita PermissionArguments ou (user, tenant)."""
        if params and isinstance(params[0], PermissionArguments):
            return self._check_account_blocks_args(params[0])

        # Forma legada: (user, tenant) -> tuple[bool, str]
        user, tenant = params[0], params[1]
        try:
            from core.models import TenantUser  # noqa: PLC0415

            TenantUser.objects.get(user=user, tenant=tenant)
            if not getattr(user, "is_active", True):
                return False, "Usuário inativo"
        except Exception as exc:  # noqa: BLE001
            from core.models import TenantUser  # noqa: PLC0415

            if isinstance(exc, TenantUser.DoesNotExist):
                return False, "Usuário não pertence ao tenant"
            logger.debug("Falha ao buscar TenantUser (legacy): %s", exc)
            return False, "Erro ao validar TenantUser"
        try:
            from portal_fornecedor.models import AcessoFornecedor  # noqa: PLC0415

            acesso = AcessoFornecedor.objects.get(usuario=user, fornecedor__tenant=tenant)
            if not acesso.pode_acessar_portal():
                return False, "Acesso ao portal bloqueado"
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignorando checagem de portal fornecedor (legacy): %s", exc)
        return True, "Conta ativa"

    def _check_custom_permissions(self, args: PermissionArguments) -> PermissionResult | None:
        """Verifica permissões personalizadas (Allow/Deny)."""
        try:
            qs = self._build_custom_permission_query(args.user, args.action)
            tenant_id = getattr(args.tenant, "id", None)
            perms = self._score_and_filter_permissions(list(qs), args.resource, tenant_id)

            if not perms:
                return None

            # A primeira permissão na lista ordenada por score decide
            best_perm = perms[0]
            # Razão padronizada para compatibilidade com testes
            suffix = f" (regra {best_perm.id})" if getattr(best_perm, "id", None) else ""
            reason = f"Permissão personalizada{suffix}"
            return PermissionResult(
                allowed=best_perm.concedida,
                source=PermissionSource.PERSONALIZADA,
                reason=reason,
            )
        except (ImportError, AttributeError) as e:
            logger.warning("Erro ao verificar permissões personalizadas: %s", e)
            return None

    def _build_custom_permission_query(
        self,
        user: UserType,
        action: str,
    ) -> QuerySet[PermissaoPersonalizadaType]:
        """Constrói a query base para buscar permissões personalizadas."""
        from user_management.models import PermissaoPersonalizada  # noqa: PLC0415

        now = timezone.now()
        qs = PermissaoPersonalizada.objects.filter(user=user).filter(
            Q(data_expiracao__isnull=True) | Q(data_expiracao__gte=now),
        )
        verb, modulo = action.split("_", 1) if "_" in action else (action, None)
        if modulo:
            qs = qs.filter(modulo__iexact=modulo)
        return qs.filter(Q(acao__iexact=verb) | Q(acao__iexact=action))

    def _score_and_filter_permissions(
        self,
        permissions: list[PermissaoPersonalizadaType],
        resource: Any | None,  # noqa: ANN401
        tenant_id: int | None,
    ) -> list[PermissaoPersonalizadaType]:
        """Pontua e filtra permissões com base na especificidade do recurso."""
        scored = []

        for p in permissions:
            score = self._calculate_permission_score(p, resource, tenant_id)
            if score >= 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]

    def _calculate_permission_score(
        self,
        perm: PermissaoPersonalizadaType,
        resource: Any | None,  # noqa: ANN401
        tenant_id: int | None,
    ) -> int:
        """Calcula o score de uma única permissão baseada na sua especificidade."""
        score = 100 if not perm.concedida else 0  # Deny tem precedência

        # Escopo do Tenant (comparar com tenant_id correto)
        if perm.scope_tenant_id is not None:
            if tenant_id is None:
                return -1  # não aplicável sem tenant
            if perm.scope_tenant_id != tenant_id:
                return -1  # regra de outro tenant
            score += 50
        else:
            score += 5  # regra global recebe bônus pequeno

        # Escopo do Recurso (string match)
        if getattr(perm, "recurso", None):
            res_str = None
            if resource is not None:
                res_str = resource if isinstance(resource, str) else str(resource)
            if res_str and perm.recurso == res_str:
                score += 20
            else:
                return -1
        return score

    def _check_role_permissions(self, args: PermissionArguments) -> PermissionResult | None:
        """Verifica permissões baseadas em Roles."""
        # Primeiro verifique se a ação exige tokens de role; se não exigir, delegue.
        action_map = self._get_action_map(args.tenant)
        required_perms = action_map.get(args.action, [])
        if not required_perms:
            return None

        role = None
        try:
            from core.models import TenantUser  # noqa: PLC0415

            tenant_user = TenantUser.objects.get(user=args.user, tenant=args.tenant)
            role = tenant_user.role
            if not role:
                return PermissionResult(
                    allowed=False,
                    source=PermissionSource.ROLE,
                    reason="Role não atribuída no tenant",
                )
        except TenantUser.DoesNotExist:
            return PermissionResult(
                allowed=False,
                source=PermissionSource.ROLE,
                reason="Usuário sem TenantUser associado",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Erro ao buscar TenantUser para '%s': %s", args.user, e)
            return PermissionResult(
                allowed=False,
                source=PermissionSource.ROLE,
                reason="Erro ao verificar role (DB)",
            )

        # role não é None aqui
        allowed = False
        reason = f"Role {getattr(role, 'name', '?')} não permite {args.action}"
        is_admin_flag = getattr(role, "name", "").lower() in {"admin", "superadmin", "owner"}

        for perm in required_perms:
            if perm == "is_admin" and is_admin_flag:
                allowed = True
                reason = f"Role {role.name} (implicit admin) permite {args.action}"
                break
            if hasattr(role, perm) and getattr(role, perm):
                allowed = True
                reason = f"Role {role.name} permite {args.action}"
                break

        return PermissionResult(allowed=allowed, source=PermissionSource.ROLE, reason=reason)
        # (não alcançado)

    # (Removido wrapper duplicado de _get_action_map)

    def clear_cache_for_user(self, user: UserType, tenant: TenantType) -> None:
        """Incrementa a versão do cache para um usuário/tenant, invalidando-o."""
        user_id = getattr(user, "id", None)
        tenant_id = getattr(tenant, "id", None)
        if user_id is not None and tenant_id is not None:
            version_key = f"{self.cache_prefix}:ver:{user_id}:{tenant_id}"
            try:
                cache.incr(version_key)
            except ValueError:
                cache.set(version_key, 1, self.CACHE_TTL)

    def invalidate_action_map(self) -> None:
        """Invalida o cache do mapa de ações."""
        self._action_map_cache_ts = 0.0

    # ---------- API pública compatível ----------
    def list_pipeline_steps(self) -> list[str]:
        """Compat: retorna os nomes dos steps configurados (mutável em testes)."""
        if not hasattr(self, "pipeline"):
            # pipeline mínima: role -> default
            self.pipeline = ["_step_role", "_step_default"]
        return list(self.pipeline)

    def add_pipeline_step(self, name: str, position: int | None = None) -> bool:
        """Adiciona um step ao pipeline (compat). Retorna True se inseriu."""
        steps = self.list_pipeline_steps()
        if name in steps:
            return False
        if position is None or position >= len(steps):
            steps.append(name)
        else:
            steps.insert(max(0, position), name)
        self.pipeline = steps
        # Bump era global para invalidar cache baseado na ordem do pipeline
        self._bump_global_era()
        return True

    def remove_pipeline_step(self, name: str) -> bool:
        """Remove um step do pipeline (compat). Retorna True se removeu."""
        steps = self.list_pipeline_steps()
        if name not in steps:
            return False
        steps.remove(name)
        self.pipeline = steps
        # Bump era global para refletir alteração
        self._bump_global_era()
        return True

    def _bump_user_tenant_version(self, user_id: int, tenant_id: int) -> None:
        vkey = f"{self.cache_prefix}:ver:{user_id}:{tenant_id}"
        try:
            cache.incr(vkey)
        except ValueError:
            cache.set(vkey, 1, self.CACHE_TTL)

    def invalidate_cache(self, user_id: int | None = None, tenant_id: int | None = None) -> None:
        """Compat: invalida caches por combinação de user/tenant.

        Sem parâmetros: bump global. Com apenas um parâmetro, atualiza todas as
        combinações relacionadas.
        """
        if user_id and tenant_id:
            self._bump_user_tenant_version(user_id, tenant_id)
            return
        if user_id and not tenant_id:
            try:
                from core.models import TenantUser  # noqa: PLC0415

                tids = TenantUser.objects.filter(user_id=user_id).values_list("tenant_id", flat=True)
                for tid in tids:
                    self._bump_user_tenant_version(user_id, int(tid))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Falha ao invalidar por usuário: %s", exc)
            return
        if tenant_id and not user_id:
            try:
                from core.models import TenantUser  # noqa: PLC0415

                uids = TenantUser.objects.filter(tenant_id=tenant_id).values_list("user_id", flat=True)
                for uid in uids:
                    self._bump_user_tenant_version(int(uid), tenant_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Falha ao invalidar por tenant: %s", exc)
            return
        # Sem parâmetros: bump global e invalida hash do action map
        self._bump_global_era()
        self._action_map_hash_cache = None

    def resolve(  # noqa: C901, PLR0911
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: Any | None = None,  # noqa: ANN401
        _context: dict | None = None,
        *,
        _force_trace: bool = False,
    ) -> tuple[bool, str]:
        """Compat: retorna (allowed, reason) e usa cache com chave distinta."""
        # Validação inicial via PermissionArguments
        args = PermissionArguments(
            user=user,
            tenant=tenant,
            action=action,
            resource=resource,
            trace_enabled=_force_trace or getattr(settings, "PERMISSION_RESOLVER_TRACE", False),
        )
        trace_steps: list[str] | None = [] if args.trace_enabled else None
        cache_key = self._get_cache_key(args, mode="res")

        first_cache = self._legacy_cache_get(cache_key, trace_steps)
        if first_cache is not None:
            return self._augment_trace(first_cache, trace_steps, source=str(PermissionSource.CACHE))

        try:
            block_tuple = self._legacy_account_blocks(user, tenant, cache_key, trace_steps)
            if block_tuple is not None:
                return self._augment_trace(block_tuple, trace_steps, source=str(PermissionSource.ACCOUNT_BLOCK))

            custom_t = self._legacy_custom(args, cache_key, trace_steps)
            if custom_t is not None:
                return self._augment_trace(custom_t, trace_steps, source=str(PermissionSource.PERSONALIZADA))

            # Guard compat: se ação exige role e usuário não possui role, negar cedo
            try:
                action_tokens = self._get_action_map(tenant).get(action, [])
                if action_tokens:
                    from core.models import TenantUser  # noqa: PLC0415

                    tu = TenantUser.objects.get(user=user, tenant=tenant)
                    if not getattr(tu, "role", None):
                        if trace_steps is not None:
                            trace_steps.append("role_deny")
                            trace_steps.append("default_result")
                        early = (False, "Role não atribuída no tenant")
                        cache.set(cache_key, early, self.CACHE_TTL)
                        return self._augment_trace(early, trace_steps, source=str(PermissionSource.ROLE))
            except Exception as exc:  # noqa: BLE001
                # Qualquer erro nessa checagem não deve impedir o fluxo normal do pipeline, apenas registremos.
                logger.debug("Early role guard check falhou: %s", exc)

            pipeline_out = self._legacy_pipeline(
                user,
                tenant,
                action,
                resource,
                (cache_key, trace_steps),
            )
            if pipeline_out is not None:
                allowed, reason, src = pipeline_out
                return self._augment_trace((allowed, reason), trace_steps, source=src)

            # Default deny se pipeline exaurida
            if trace_steps is not None:
                trace_steps.append("default_result")
            out2 = (False, "Ação não permitida (default)")
            cache.set(cache_key, out2, self.CACHE_TTL)
            return self._augment_trace(out2, trace_steps, source=str(PermissionSource.DEFAULT))
        except Exception as exc:  # pragma: no cover - caminho de exceção compat
            logger.exception("Erro ao resolver permissão")
            if trace_steps is not None:
                trace_steps.append(f"exception:{exc}")
            out3 = (False, f"Erro interno: {exc}")
            return self._augment_trace(out3, trace_steps, source=str(PermissionSource.EXCEPTION))

    def _legacy_cache_get(self, cache_key: str, trace_steps: list[str] | None) -> tuple[bool, str] | None:
        cached = cache.get(cache_key)
        if cached is None:
            return None
        try:
            allowed, reason = cached
            if trace_steps is not None:
                trace_steps.append("cache_hit")
            return bool(allowed), str(reason)
        except (TypeError, ValueError) as exc:  # pragma: no cover
            logger.debug("Falha ao ler tupla do cache '%s': %s", cache_key, exc)
            return None

    def _legacy_account_blocks(
        self,
        user: UserType,
        tenant: TenantType,
        cache_key: str,
        trace_steps: list[str] | None,
    ) -> tuple[bool, str] | None:
        bloqueio = self._check_account_blocks(user, tenant)
        if isinstance(bloqueio, tuple) and not bloqueio[0]:
            if trace_steps is not None:
                trace_steps.append(f"account_blocks:{bloqueio[1]}")
            out = (False, bloqueio[1])
            cache.set(cache_key, out, self.CACHE_TTL // 2)
            return out
        return None

    def _legacy_custom(
        self,
        args: PermissionArguments,
        cache_key: str,
        trace_steps: list[str] | None,
    ) -> tuple[bool, str] | None:
        res = self._check_custom_permissions(args)
        if res is None:
            return None
        msg = res.reason or "Permissão personalizada"
        if trace_steps is not None:
            trace_steps.append("personalizada")
        out = (res.allowed, msg)
        cache.set(cache_key, out, self.CACHE_TTL)
        return out

    def _legacy_pipeline(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: str | None,
        ctx: tuple[str, list[str] | None],
    ) -> tuple[bool, str, str] | None:
        cache_key, trace_steps = ctx
        expected_step_tuple_len = 3
        for step_name in self.list_pipeline_steps():
            step = getattr(self, step_name, None)
            if not callable(step):
                continue
            result_step = step(user, tenant, action, resource, None)
            if result_step is None:
                continue
            if not isinstance(result_step, tuple) or len(result_step) != expected_step_tuple_len:  # segurança
                continue
            allow, msg, src = result_step
            if trace_steps is not None:
                trace_steps.append(f"{src}_{'allow' if allow else 'deny'}")
                if src == "default":
                    trace_steps.append("default_result")
            tup = (bool(allow), str(msg))
            cache.set(cache_key, tup, self.CACHE_TTL)
            return (tup[0], tup[1], src)
        return None

    def resolve_decision(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        resource: Any | None = None,  # noqa: ANN401
        _context: dict | None = None,
        *,
        _force_trace: bool = False,
    ) -> PermissionDecision:
        """Compat: retorna objeto de decisão detalhado."""
        res = self.explain_permission(user, tenant, action, resource, _force_trace=_force_trace)
        trace = None
        if getattr(settings, "PERMISSION_RESOLVER_TRACE", False) or _force_trace:
            trace = "|".join(self._last_trace_lines) if self._last_trace_lines else ""
        return PermissionDecision(allowed=res.allowed, reason=res.reason, trace=trace, source=res.source)

    # ---------- Steps compatíveis ----------
    def _step_role(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        _resource: Any | None = None,  # noqa: ANN401
        _context: dict | None = None,
    ) -> tuple[bool, str, str] | None:
        """Verifica permissões baseadas em Role + tokens do action map (compat)."""
        # Primeiro verifica se a ação exige algum token de role; se não exigir, delega.
        tokens = self._get_action_map(tenant).get(action, [])
        if not tokens:
            return None

        try:
            from core.models import TenantUser  # noqa: PLC0415

            tenant_user = TenantUser.objects.get(user=user, tenant=tenant)
            role = tenant_user.role
            if not role:
                return False, "Role não atribuída no tenant", "role"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erro ao obter TenantUser: %s", exc)
            return False, "Usuário sem TenantUser associado", "role"
        is_admin_flag = isinstance(getattr(role, "name", None), str) and role.name.lower() in {
            "admin",
            "superadmin",
            "owner",
        }

        if "is_admin" in tokens and is_admin_flag:
            allowed, msg = True, f"Role {role.name} (implicit admin) permite {action}"
            return allowed, msg, "role"

        for perm in tokens:
            if perm == "is_admin":
                continue
            if hasattr(role, perm) and getattr(role, perm):
                allowed, msg = True, f"Role {role.name} permite {action}"
                return allowed, msg, "role"
        allowed, msg = False, f"Role {role.name} não permite {action}"
        return allowed, msg, "role"

    def _step_default(
        self,
        _user: UserType,
        _tenant: TenantType,
        _action: str,
        _resource: Any | None = None,  # noqa: ANN401
        _context: dict | None = None,
    ) -> tuple[bool, str, str]:
        # Compat: respeitar defaults de módulo mínimas
        allowed, msg = self._check_module_defaults(_user, _tenant, _action)
        return allowed, msg, "default"

    def _step_implicit(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        _resource: Any | None = None,  # noqa: ANN401
        context: dict | None = None,
    ) -> tuple[bool, str, str] | None:
        allowed, msg = self._check_implicit_roles(user, tenant, action, context)
        if allowed:
            return True, msg, "implicit"
        return None

    # Hook padrão para testes/compatibilidade
    def _check_implicit_roles(
        self,
        user: UserType,
        tenant: TenantType,
        action: str,
        _context: dict | None = None,
    ) -> tuple[bool, str]:
        # Fornecedor
        try:
            from portal_fornecedor.models import AcessoFornecedor  # noqa: PLC0415

            acesso = AcessoFornecedor.objects.get(usuario=user, fornecedor__tenant=tenant, ativo=True)
            if acesso.pode_acessar_portal():
                fornecedor_actions = [
                    "VIEW_DASHBOARD_FORNECEDOR",
                    "VIEW_COTACAO",
                    "SUBMIT_PROPOSTA",
                    "VIEW_PROPOSTA",
                ]
                if action in fornecedor_actions:
                    return True, "Acesso de fornecedor"
                if getattr(acesso, "is_admin_portal", False) and action in ["MANAGE_FORNECEDOR_USERS"]:
                    return True, "Admin portal fornecedor"
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignorando checagem de papel implícito fornecedor: %s", exc)

        # Cliente
        try:
            from portal_cliente.models import ContaCliente  # noqa: PLC0415

            conta = ContaCliente.objects.filter(usuario=user, cliente__tenant=tenant, ativo=True).first()
            if conta and conta.pode_acessar_portal():
                cliente_actions = ["VIEW_DASHBOARD_CLIENTE", "VIEW_DOCUMENTOS_CLIENTE", "VIEW_ORCAMENTOS"]
                if action in cliente_actions:
                    return True, "Acesso cliente"
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignorando checagem de papel implícito cliente: %s", exc)
        return False, "Sem papel implícito"

    def _check_module_defaults(self, _user: UserType, _tenant: TenantType, action: str) -> tuple[bool, str]:
        default_actions = {
            "VIEW_DASHBOARD_PUBLIC": True,
        }
        if action in default_actions:
            return default_actions[action], "Default do módulo"
        return False, "Ação não permitida (default)"

    def _augment_trace(
        self,
        result: tuple[bool, str],
        trace_steps: list[str] | None,
        *,
        source: str | None = None,
    ) -> tuple[bool, str]:
        if trace_steps is None:
            return result
        allowed, reason = result
        trace_str = ">".join(trace_steps)
        out = f"{reason}|trace={trace_str}"
        if source:
            out = f"{reason}|src={source}|trace={trace_str}"
        # Guardar para resolve_decision
        self._last_trace_lines = trace_steps
        return allowed, out

    # Hook padrão para testes/compatibilidade; pode ser monkey-patched
    def _check_implicit_roles_args(self, _args: PermissionArguments) -> PermissionResult | None:
        return None


# Instância singleton
permission_resolver = PermissionResolver()


def has_permission(
    user: UserType,
    tenant: TenantType,
    action: str,
    resource: Any | None = None,  # noqa: ANN401
) -> bool:
    """Função de atalho para a instância singleton do resolver."""
    return permission_resolver.explain_permission(user, tenant, action, resource).allowed


def explain_permission(
    user: UserType,
    tenant: TenantType,
    action: str,
    resource: Any | None = None,  # noqa: ANN401
) -> PermissionResult:
    """Função de atalho para a instância singleton do resolver que retorna a decisão detalhada."""
    return permission_resolver.explain_permission(user, tenant, action, resource, _force_trace=True)


def permission_required(action: str, resource_getter: Callable | None = None) -> Callable:
    """Decorador para proteger views com base em permissões."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(
            request: HttpRequest,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> HttpResponse:
            user = request.user
            tenant = getattr(request, "tenant", None)
            resource = resource_getter(request, *args, **kwargs) if resource_getter else None

            if not has_permission(user, tenant, action, resource):
                return HttpResponseForbidden("Acesso negado.")

            return func(request, *args, **kwargs)

        return wrapper

    return decorator

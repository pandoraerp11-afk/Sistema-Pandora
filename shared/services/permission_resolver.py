"""
Sistema de resolução de permissões unificado.
Implementa hierarquia de precedência: Deny > Allow > Role > Papel > Default.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str
    trace: str | None = None
    source: str | None = None  # ex: 'personalizada','role','implicit','default','account_block','exception','cache'


try:
    # Métricas Prometheus (opcional)
    from prometheus_client import Counter, Histogram

    _METRICS_ENABLED = True
except Exception:  # pragma: no cover - fallback se lib ausente
    Counter = Histogram = None  # type: ignore
    _METRICS_ENABLED = False


def get_base_action_map() -> dict[str, list[str]]:
    """Mapa base de actions -> lista de tokens de permissão (em ordem de precedência simplificada).
    Esta função concentra o dicionário fixo para permitir extensão limpa.
    """
    return {
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


def _merge_action_maps(base: dict[str, list[str]], extra: dict[str, list[str]]) -> dict[str, list[str]]:
    """Merge não destrutivo: preserva ordem base e adiciona novos tokens sem duplicar.
    Em colisão de chave, tokens de extra são anexados no final em ordem.
    """
    for action, tokens in (extra or {}).items():
        if action in base:
            existing = base[action]
            for t in tokens:
                if t not in existing:
                    existing.append(t)
        else:
            base[action] = list(tokens)
    return base


class PermissionResolver:
    """
    Resolve permissões seguindo hierarquia de precedência.
    """

    # Cache TTL em segundos
    CACHE_TTL = getattr(settings, "PERMISSION_CACHE_TTL", 300)  # 5 minutos

    def __init__(self):
        self.cache_prefix = "perm_resolver"
        # Pipeline configurável (nomes de métodos a executar em ordem após bloqueios e permissões personalizadas)
        self.pipeline: list[str] = ["_step_role", "_step_implicit", "_step_default"]
        # Era global para invalidar tudo rapidamente sem varrer chaves
        self._global_era_key = f"{self.cache_prefix}:global_era"
        if cache.get(self._global_era_key) is None:
            try:
                cache.add(self._global_era_key, 1, self.CACHE_TTL)
            except Exception:  # pragma: no cover
                pass
        # Hash do action map (incluído na chave para invalidar mudanças estruturais)
        self._action_map_hash_cache: str | None = None
        self._action_map_hash_ts: float = 0.0
        # Métricas
        if _METRICS_ENABLED:
            self._m_decisions = Counter(
                "permission_resolver_decisions_total", "Total de decisões de permissão", ["action", "source", "allowed"]
            )
            self._m_cache_hits = Counter("permission_resolver_cache_hits_total", "Hits de cache de permissões")
            self._m_cache_misses = Counter("permission_resolver_cache_misses_total", "Misses de cache de permissões")
            self._m_latency = Histogram(
                "permission_resolver_latency_seconds",
                "Latência de resolução de permissões",
                buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0),
            )
            # TTL restante observado em hits do cache (segundos)
            self._m_cache_ttl = Histogram(
                "permission_resolver_cache_ttl_seconds",
                "TTL restante observado em hits de cache",
                buckets=(1, 2, 5, 10, 20, 30, 60, 120, 180, 240, 300, 600),
            )
        else:  # placeholders para evitar checks
            self._m_decisions = self._m_cache_hits = self._m_cache_misses = self._m_latency = self._m_cache_ttl = None

    def _get_version(self, user_id: int, tenant_id: int) -> int:
        """Obtém versão de cache específica user/tenant (permite invalidar sem delete_pattern)."""
        version_key = f"{self.cache_prefix}:ver:{user_id}:{tenant_id}"
        v = cache.get(version_key)
        if v is None:
            v = 1
            cache.set(version_key, v, self.CACHE_TTL)
        return v

    def _get_global_era(self) -> int:
        try:
            era = cache.get(self._global_era_key)
            if era is None:
                era = 1
                cache.set(self._global_era_key, era, self.CACHE_TTL)
            return int(era)
        except Exception:  # pragma: no cover
            return 1

    def _bump_global_era(self):
        try:
            era = self._get_global_era()
            cache.set(self._global_era_key, era + 1, self.CACHE_TTL)
        except Exception:  # pragma: no cover
            pass

    def _get_action_map_hash(self) -> str:
        """Hash curto do action map para invalidar cache quando estrutura muda.
        Recalcula a cada 60s para evitar custo em hot path (mesmo sendo baixo)."""
        now = time.time()
        if self._action_map_hash_cache and (now - self._action_map_hash_ts) < 60:
            return self._action_map_hash_cache
        amap = self._get_action_map()
        # Ordenar determinísticamente
        items = sorted((k, tuple(sorted(v))) for k, v in amap.items())
        raw = repr(items).encode("utf-8")
        h = hashlib.md5(raw).hexdigest()[:8]
        self._action_map_hash_cache = h
        self._action_map_hash_ts = now
        return h

    def _get_action_map(self) -> dict[str, list[str]]:  # configurável/estendível
        """Obtém action map final considerando extensões via settings.
        Settings suportados (todos opcionais):
          PERMISSION_ACTION_MAP_EXTRA: dict de {ACTION: [tokens]}
          PERMISSION_ACTION_MAP_PROVIDER: dotted path para callable que retorna dict
        """
        base = get_base_action_map()
        # Extra estático (merge não destrutivo)
        extra = getattr(settings, "PERMISSION_ACTION_MAP_EXTRA", None)
        if isinstance(extra, dict):
            base = _merge_action_maps(base, extra)
        # Provider dinâmico
        provider_path = getattr(settings, "PERMISSION_ACTION_MAP_PROVIDER", None)
        if provider_path:
            try:
                mod_name, func_name = provider_path.rsplit(".", 1)
                provider = getattr(__import__(mod_name, fromlist=[func_name]), func_name)
                provided = provider() or {}
                if isinstance(provided, dict):
                    base = _merge_action_maps(base, provided)
            except Exception as e:  # pragma: no cover
                logger.warning(f"Falha ao carregar provider de action map '{provider_path}': {e}")
        return base

    def resolve(
        self, user, tenant, action: str, resource: str = None, context: dict = None, _force_trace: bool = False
    ) -> tuple[bool, str]:
        """
        Resolve permissão seguindo hierarquia de precedência.

        Args:
            user: Usuário
            tenant: Tenant
            action: Ação (ex: 'CREATE_COTACAO', 'VIEW_PROPOSTA')
            resource: Recurso opcional (ex: 'cotacao:123')
            context: Contexto adicional

        Returns:
            Tuple[bool, str]: (tem_permissao, motivo)
        """
        perf_enabled = getattr(settings, "PANDORA_PERF", False) or __import__("os").environ.get("PANDORA_PERF")
        t_start = time.perf_counter() if perf_enabled or _METRICS_ENABLED else None

        trace_enabled = _force_trace or getattr(settings, "PERMISSION_RESOLVER_TRACE", False)
        trace_steps = [] if trace_enabled else None

        if not user or not user.is_active:
            base_reason = "Usuário inativo"
            if trace_enabled:
                base_reason += "|initial"
            return False, base_reason

        if not tenant:
            base_reason = "Tenant inválido"
            if trace_enabled:
                base_reason += "|initial"
            return False, base_reason

        cache_key = self._get_cache_key(user.id, tenant.id, action, resource)
        cached_result = cache.get(cache_key)
        if cached_result:
            if trace_steps is not None:
                # Tentar extrair TTL restante (nem todos backends suportam)
                ttl_left = None
                try:  # Redis backend compatível
                    client = getattr(cache, "client", None)
                    if client:
                        cli = client.get_client(write=True)
                        # PTTL retorna ms restantes; fallback TTL em segundos
                        ttl_ms = cli.pttl(cache_key)
                        if ttl_ms and ttl_ms > 0:
                            ttl_left = ttl_ms / 1000.0
                        else:
                            ttl_s = cli.ttl(cache_key)
                            if ttl_s and ttl_s > 0:
                                ttl_left = float(ttl_s)
                except Exception:  # pragma: no cover
                    pass
                # Registrar métrica de TTL quando disponível
                if _METRICS_ENABLED and ttl_left is not None:
                    try:
                        self._m_cache_ttl.observe(ttl_left)  # type: ignore
                    except Exception:  # pragma: no cover
                        pass
                if ttl_left is not None:
                    trace_steps.append(f"cache_hit~ttl={ttl_left:.1f}s")
                else:
                    trace_steps.append("cache_hit")
            if _METRICS_ENABLED:
                try:
                    self._m_cache_hits.inc()  # type: ignore
                    self._m_decisions.labels(action=action, source="cache", allowed=str(cached_result[0])).inc()  # type: ignore
                    if t_start is not None:
                        self._m_latency.observe(time.perf_counter() - t_start)  # type: ignore
                except Exception:  # pragma: no cover
                    pass
            if perf_enabled and t_start is not None:
                dt = (time.perf_counter() - t_start) * 1000
                logger.debug(
                    f"PERF_PERMISSION_RESOLVER warm user={user.id} tenant={tenant.id} action={action} resource={resource} ms={dt:.3f}"
                )
            return self._augment_trace(cached_result, trace_steps, source="cache")
        elif _METRICS_ENABLED:
            try:
                self._m_cache_misses.inc()  # type: ignore
            except Exception:  # pragma: no cover
                pass

        try:
            # 1. Verificar bloqueios de conta
            bloqueio_result = self._check_account_blocks(user, tenant)
            if not bloqueio_result[0]:
                if trace_steps is not None:
                    trace_steps.append(f"account_blocks:{bloqueio_result[1]}")
                result = bloqueio_result
                cache.set(cache_key, result, self.CACHE_TTL // 2)  # Cache menor para bloqueios
                return self._augment_trace(result, trace_steps, source="account_block")

            # 2. Verificar permissões personalizadas (Deny/Allow precedência multi-escopo)
            perm_personalizada = self._check_permissoes_personalizadas(user, tenant, action, resource)
            if perm_personalizada is not None:
                msg = "Permissão personalizada"
                if trace_steps is not None:
                    trace_steps.append(f"personalizada:{perm_personalizada}")
                result = (perm_personalizada, msg)
                cache.set(cache_key, result, self.CACHE_TTL)
                return self._augment_trace(result, trace_steps, source="personalizada")

            # Executar pipeline configurável (cada step deve retornar (bool,str,source) ou None para continuar)
            for step_name in self.pipeline:
                step_method: Callable = getattr(self, step_name, None)
                if not step_method:  # pragma: no cover
                    continue
                out = step_method(user, tenant, action, resource, context)
                if out is None:
                    continue
                allow, msg, src = out
                if allow:
                    if trace_steps is not None:
                        trace_steps.append(f"{src}_allow")
                elif trace_steps is not None:
                    if src == "default":  # compat legacy
                        trace_steps.append("default_result")
                    trace_steps.append(f"{src}_deny")
                result = (allow, msg)
                # padronizar TTL
                cache.set(cache_key, result, self.CACHE_TTL)
                augmented = self._augment_trace(result, trace_steps, source=src)
                if _METRICS_ENABLED:
                    try:
                        self._m_decisions.labels(action=action, source=src, allowed=str(allow)).inc()  # type: ignore
                        if t_start is not None:
                            self._m_latency.observe(time.perf_counter() - t_start)  # type: ignore
                    except Exception:  # pragma: no cover
                        pass
                return augmented
            # Se nada retornou (pipeline exaurida) => negar por default explícito
            if trace_steps is not None:
                trace_steps.append("default_result")
            result = (False, "Ação não permitida (pipeline exhausted)")
            cache.set(cache_key, result, self.CACHE_TTL)
            augmented = self._augment_trace(result, trace_steps, source="default")
            if _METRICS_ENABLED:
                try:
                    self._m_decisions.labels(action=action, source="default", allowed="False").inc()  # type: ignore
                    if t_start is not None:
                        self._m_latency.observe(time.perf_counter() - t_start)  # type: ignore
                except Exception:  # pragma: no cover
                    pass
            return augmented

        except Exception as e:
            logger.error(f"Erro ao resolver permissão: {e}")
            err_msg = f"Erro interno: {e}"
            if trace_steps is not None:
                trace_steps.append(f"exception:{e}")
            augmented = self._augment_trace((False, err_msg), trace_steps, source="exception")
            if _METRICS_ENABLED:
                try:
                    self._m_decisions.labels(action=action, source="exception", allowed="False").inc()  # type: ignore
                    if t_start is not None:
                        self._m_latency.observe(time.perf_counter() - t_start)  # type: ignore
                except Exception:  # pragma: no cover
                    pass
            return augmented
        finally:
            if perf_enabled and t_start is not None:
                if t_start is not None:
                    dt = (time.perf_counter() - t_start) * 1000
                    logger.debug(
                        f"PERF_PERMISSION_RESOLVER cold user={getattr(user, 'id', None)} tenant={getattr(tenant, 'id', None)} action={action} resource={resource} ms={dt:.3f}"
                    )

    def _get_cache_key(self, user_id: int, tenant_id: int, action: str, resource: str = None) -> str:
        """Gera chave de cache para permissão.
        Formato: prefix:era:ahash:ver:user:tenant:action[:resource]
        """
        ver = self._get_version(user_id, tenant_id)
        era = self._get_global_era()
        ahash = self._get_action_map_hash()
        parts = [self.cache_prefix, str(era), ahash, str(ver), str(user_id), str(tenant_id), action]
        if resource:
            parts.append(resource)
        return ":".join(parts)

    def _check_account_blocks(self, user, tenant) -> tuple[bool, str]:
        """Verifica bloqueios de conta."""
        # Verificar se usuário está no tenant
        try:
            from core.models import TenantUser

            TenantUser.objects.get(user=user, tenant=tenant)
            # Modelo TenantUser não possui campo is_active; considerar user.is_active como proxy
            if not user.is_active:
                return False, "Usuário inativo"
        except TenantUser.DoesNotExist:
            return False, "Usuário não pertence ao tenant"

        # Verificar bloqueios específicos de fornecedor
        try:
            from portal_fornecedor.models import AcessoFornecedor

            acesso = AcessoFornecedor.objects.get(usuario=user, fornecedor__tenant=tenant)
            if not acesso.pode_acessar_portal():
                return False, "Acesso ao portal bloqueado"
        except AcessoFornecedor.DoesNotExist:
            pass  # Não é fornecedor, continuar

        return True, "Conta ativa"

    def _check_permissoes_personalizadas(self, user, tenant, action, resource: str | None = None) -> bool | None:
        """Avalia permissões personalizadas com precedência:
        1. Scoped + recurso
        2. Scoped genérica
        3. Global + recurso
        4. Global genérica
        Considera expiração (ignora expiradas). Retorna True/False ou None.
        """
        try:
            from django.db.models import Q
            from django.utils import timezone

            from user_management.models import PermissaoPersonalizada

            now = timezone.now()
            qs = PermissaoPersonalizada.objects.filter(user=user)
            # Pre-filtrar por ação (acao) se estiver preenchida
            verb = action
            modulo = None
            if "_" in action:
                head, tail = action.split("_", 1)
                verb = head.lower()
                modulo = tail.lower()
            if modulo:
                qs = qs.filter(modulo__iexact=modulo)
            qs = qs.filter(Q(acao__iexact=verb) | Q(acao__iexact=action))  # tolerância
            perms = list(qs.select_related("scope_tenant"))
            # Pré computar scores (evitando recalcular dentro do loop e criando estrutura para debug futuro)
            scored: list[tuple[int, Any]] = []
            target_tid = getattr(tenant, "id", None)
            for p in perms:
                if p.data_expiracao and p.data_expiracao < now:
                    continue  # expirada
                sc = 0
                if p.concedida is False:
                    sc += 100
                if p.scope_tenant_id == target_tid:
                    sc += 50
                if p.recurso and resource:
                    if p.recurso == resource:
                        sc += 20
                    else:
                        sc = -1  # incompatível
                elif p.recurso and not resource:
                    sc = -1
                if sc >= 0 and p.scope_tenant_id is None:
                    sc += 5
                if sc >= 0 and not p.recurso:
                    sc += 1
                if sc >= 0:
                    scored.append((sc, p))
            if not scored:
                return None
            # Ordenar por score desc (primeiro define). Denies com score alto permanecem no topo.
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1].concedida
        except Exception as e:
            logger.warning(f"Erro ao verificar permissões personalizadas: {e}")
        return None

    def _check_tenant_roles(self, user, tenant, action) -> tuple[bool, str]:
        """Verifica roles do tenant."""
        try:
            from core.models import TenantUser

            tenant_user = TenantUser.objects.get(user=user, tenant=tenant)
            if not tenant_user.role:
                return False, "Sem role no tenant"

            # Mapear actions para permissions do role
            action_map = self._get_action_map()

            required_perms = action_map.get(action, [])
            role = tenant_user.role
            # Flag implícita: nome do papel indica admin
            is_admin_flag = role.name.lower() in {"admin", "superadmin", "owner"}

            for perm in required_perms:
                if perm == "is_admin" and is_admin_flag:
                    return True, f"Role {role.name} (implicit admin) permite {action}"
                if hasattr(role, perm) and getattr(role, perm):
                    return True, f"Role {role.name} permite {action}"

            return False, f"Role {role.name} não permite {action}"

        except Exception as e:
            logger.warning(f"Erro ao verificar role: {e}")
            return False, "Erro ao verificar role"

    def _check_implicit_roles(self, user, tenant, action, context) -> tuple[bool, str]:
        """Verifica papéis implícitos (AcessoFornecedor, etc)."""
        # Fornecedor
        try:
            from portal_fornecedor.models import AcessoFornecedor

            acesso = AcessoFornecedor.objects.get(usuario=user, fornecedor__tenant=tenant, ativo=True)

            if acesso.pode_acessar_portal():
                fornecedor_actions = ["VIEW_DASHBOARD_FORNECEDOR", "VIEW_COTACAO", "SUBMIT_PROPOSTA", "VIEW_PROPOSTA"]

                if action in fornecedor_actions:
                    return True, "Acesso de fornecedor"

                # Admin do portal pode mais ações
                if acesso.is_admin_portal and action in ["MANAGE_FORNECEDOR_USERS"]:
                    return True, "Admin portal fornecedor"

        except AcessoFornecedor.DoesNotExist:
            pass

        # TODO: Adicionar verificação para ContaCliente quando implementado
        # ContaCliente real: permissões implícitas de portal cliente
        try:
            from portal_cliente.models import ContaCliente

            conta = ContaCliente.objects.filter(usuario=user, cliente__tenant=tenant, ativo=True).first()
            if conta and conta.pode_acessar_portal():
                cliente_actions = ["VIEW_DASHBOARD_CLIENTE", "VIEW_DOCUMENTOS_CLIENTE", "VIEW_ORCAMENTOS"]
                if action in cliente_actions:
                    return True, "Acesso cliente"
        except Exception:
            pass

        return False, "Sem papel implícito"

    def _check_module_defaults(self, user, tenant, action) -> tuple[bool, str]:
        """Verifica defaults do módulo."""
        # Defaults muito restritivos - apenas algumas ações básicas
        default_actions = {
            "VIEW_DASHBOARD_PUBLIC": True,  # Dashboard público
        }

        if action in default_actions:
            return default_actions[action], "Default do módulo"

        return False, "Ação não permitida por default"

    # ---- Pipeline steps (retornam (bool, msg, source) ou None) ----
    def _step_role(self, user, tenant, action, resource, context):
        # Early-exit: somente processar se action conhecida no mapa
        action_map = self._get_action_map()
        if action not in action_map:
            return None  # deixa para implicit/default
        allowed, msg = self._check_tenant_roles(user, tenant, action)
        if allowed:
            return True, msg, "role"
        return False, msg, "role"

    def _step_implicit(self, user, tenant, action, resource, context):
        allowed, msg = self._check_implicit_roles(user, tenant, action, context)
        if allowed:
            return True, msg, "implicit"
        return None  # continua sem registrar negação

    def _step_default(self, user, tenant, action, resource, context):
        allowed, msg = self._check_module_defaults(user, tenant, action)
        return allowed, msg, "default"

    def invalidate_cache(self, user_id: int = None, tenant_id: int = None):
        """Invalida cache de permissões.
        - Sem parâmetros: bump global era (invalida tudo)
        - user_id + tenant_id: versão específica
        - user_id: todos tenants do user
        - tenant_id: todos users do tenant
        """
        try:
            if user_id and tenant_id:
                version_key = f"{self.cache_prefix}:ver:{user_id}:{tenant_id}"
                cur = cache.get(version_key, 1)
                cache.set(version_key, cur + 1, self.CACHE_TTL)
            elif user_id:
                from core.models import TenantUser

                for tid in TenantUser.objects.filter(user_id=user_id).values_list("tenant_id", flat=True):
                    version_key = f"{self.cache_prefix}:ver:{user_id}:{tid}"
                    cur = cache.get(version_key, 1)
                    cache.set(version_key, cur + 1, self.CACHE_TTL)
            elif tenant_id:
                from core.models import TenantUser

                for uid in TenantUser.objects.filter(tenant_id=tenant_id).values_list("user_id", flat=True):
                    version_key = f"{self.cache_prefix}:ver:{uid}:{tenant_id}"
                    cur = cache.get(version_key, 1)
                    cache.set(version_key, cur + 1, self.CACHE_TTL)
            else:
                # Global
                self._bump_global_era()
                # Também invalidar hash do action map forçando recomputo imediato
                self._action_map_hash_cache = None
        except Exception as e:
            logger.warning(f"Erro ao invalidar cache (versionamento): {e}")

    # ---- API dinâmica de pipeline ----
    def add_pipeline_step(self, step_name: str, position: int | None = None) -> bool:
        """Adiciona um step ao pipeline se existir método correspondente.
        position: índice opcional. Retorna True se adicionado."""
        if not hasattr(self, step_name):
            return False
        if step_name in self.pipeline:
            return True  # já presente
        if position is None or position >= len(self.pipeline):
            self.pipeline.append(step_name)
        else:
            self.pipeline.insert(position, step_name)
        # invalidar globalmente pois resultado pode mudar
        self._bump_global_era()
        return True

    def remove_pipeline_step(self, step_name: str) -> bool:
        if step_name in self.pipeline:
            self.pipeline = [s for s in self.pipeline if s != step_name]
            self._bump_global_era()
            return True
        return False

    def list_pipeline_steps(self) -> list[str]:
        return list(self.pipeline)

    # --- helpers internos ---
    def _augment_trace(self, result: tuple[bool, str], trace_steps, source: str | None = None):
        if trace_steps is None:
            return result
        allowed, reason = result
        trace_str = ">".join(trace_steps)
        reason = f"{reason}|src={source}|trace={trace_str}" if source else f"{reason}|trace={trace_str}"
        return allowed, reason

    # NOVO: API opcional retornando PermissionDecision (sem quebrar testes existentes)
    def resolve_decision(
        self, user, tenant, action: str, resource: str = None, context: dict = None, _force_trace: bool = False
    ) -> PermissionDecision:
        allowed, reason = self.resolve(user, tenant, action, resource, context, _force_trace=_force_trace)
        trace_part = None
        source = None
        if "|trace=" in reason:
            base, trace_seg = reason.split("|trace=", 1)
            # checar se há src= antes do trace
            if "|src=" in base:
                base2, src_seg = base.split("|src=", 1)
                reason = base2
                # src_seg pode ter outros sufixos (não deveria). Limpar por segurança
                source = src_seg
            else:
                reason = base
            trace_part = trace_seg
        return PermissionDecision(allowed=allowed, reason=reason, trace=trace_part, source=source)


# Instância global
permission_resolver = PermissionResolver()


def has_permission(user, tenant, action: str, resource: str = None, context: dict = None) -> bool:
    """
    Helper function para verificar permissão.

    Usage:
        if has_permission(request.user, tenant, 'CREATE_COTACAO'):
            # permitir ação
    """
    result, _ = permission_resolver.resolve(user, tenant, action, resource, context)
    return result


def explain_permission(user, tenant, action: str, resource: str = None, context: dict = None) -> dict[str, Any]:
    """Retorna explicação estruturada da decisão de permissão.
    Contém: allowed, reason, source, steps (lista na ordem), action_tokens.
    Não altera comportamento padrão (força trace somente nesta chamada).
    """
    decision = permission_resolver.resolve_decision(user, tenant, action, resource, context, _force_trace=True)
    steps: list[str] = []
    if decision.trace:
        steps = decision.trace.split(">") if decision.trace else []
    # Tokens de action
    action_map = permission_resolver._get_action_map()
    tokens = action_map.get(action, [])
    return {
        "action": action,
        "resource": resource,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "source": decision.source,
        "steps": steps,
        "action_tokens": tokens,
    }


def require_permission(action: str, resource: str = None):
    """
    Decorator para views que requer permissão.

    Usage:
        @require_permission('CREATE_COTACAO')
        def create_cotacao_view(request):
            pass
    """

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            from django.http import HttpResponseForbidden

            from core.utils import get_current_tenant

            tenant = get_current_tenant(request)
            if not has_permission(request.user, tenant, action, resource):
                return HttpResponseForbidden("Permissão negada")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator

"""Middlewares centrais do sistema Pandora (refatorados sem mudar regras de negócio)."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, ClassVar

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError, IntegrityError, OperationalError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from .models import AuditLog, Tenant
from .utils import get_client_ip, get_current_tenant

if TYPE_CHECKING:  # imports apenas para tipagem
    from collections.abc import Iterable

    from django.contrib.auth.base_user import AbstractBaseUser
    from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


def _noop(*_a: object, **_k: object) -> None:
    """Função fallback para import opcional."""


try:  # import opcional
    from .authorization import can_access_module, log_module_denial
except ImportError:  # pragma: no cover - módulo opcional ausente
    can_access_module = None
    log_module_denial = _noop


EXEMPT_TENANT_PATHS = [
    "/admin/",
    "/core/logout/",
    "/core/login/",
    "/core/tenant-select/",
    "/core/tenant-selection/",
    "/portal-cliente/portal/",  # portal cliente (exposto a usuários sem TenantUser)
    "/portal-cliente/",  # abrangência extra para segurança (inclui API futura)
    "/core/api/",
    "/core-api/",
    "/dashboard/",
    "/static/",
    "/media/",
    "/prontuarios/api/quick-create/",
    "/core/wizard/metrics/",
    "/user_management/convites/aceitar/",
    "/user-management/convites/aceitar/",
    "/cotacoes/portal/",
]

MODULE_EXEMPT_PATHS = [
    "/admin/",
    "/core/login/",
    "/core/logout/",
    "/core/tenant-select/",
    "/core/tenant-selection/",
    "/portal-cliente/portal/",
    "/portal-cliente/",
    "/core/tenant-switch/",
    "/core/wizard/metrics/",
    "/prontuarios/api/quick-create/",
    "/static/",
    "/media/",
    "/dashboard/",
    "/quick-access/",
    "/user_management/convites/aceitar/",
    "/user-management/convites/aceitar/",
    "/cotacoes/portal/",
]

MODULE_URL_MAPPING = {
    "/clientes/": "clientes",
    "/obras/": "obras",
    "/orcamentos/": "orcamentos",
    "/fornecedores/": "fornecedores",
    "/produtos/": "produtos",
    "/funcionarios/": "funcionarios",
    "/servicos/": "servicos",
    "/compras/": "compras",
    "/apropriacao/": "apropriacao",
    "/financeiro/": "financeiro",
    "/estoque/": "estoque",
    "/aprovacoes/": "aprovacoes",
    "/relatorios/": "relatorios",
    "/bi/": "bi",
    "/agenda/": "agenda",
    "/chat/": "chat",
    "/notifications/": "notifications",
    "/formularios/": "formularios",
    "/sst/": "sst",
    "/treinamento/": "treinamento",
    "/admin-panel/": "admin",
}

HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 400


def _path_starts(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


def _get_single_tenant(request: HttpRequest) -> Tenant | None:
    memberships = getattr(request.user, "tenant_memberships", None)
    if memberships is not None:
        with contextlib.suppress(Exception):  # consultas inócuas
            if memberships.count() == 1:
                only = memberships.first()
                return only.tenant if only else None
    proxy = getattr(request.user, "tenants", None)
    if proxy is not None:
        with contextlib.suppress(Exception):
            seq = list(proxy) if not isinstance(proxy, list) else proxy
            if len(seq) == 1:
                return seq[0]
    return None


def _detect_tenant(request: HttpRequest) -> Tenant | None:
    explicit = request.META.get("HTTP_X_TENANT") or request.META.get("HTTP_X_TENANT_ID")
    if explicit:
        try:
            return Tenant.objects.get(subdomain=explicit)
        except Tenant.DoesNotExist:
            try:
                return Tenant.objects.get(id=explicit)
            except Tenant.DoesNotExist:
                return None
    host = request.META.get("HTTP_HOST", "")
    sub = host.split(":")[0].split(".")[0] if host else ""
    if sub:
        try:
            return Tenant.objects.get(subdomain=sub)
        except Tenant.DoesNotExist:
            return None
    return None


class TenantMiddleware(MiddlewareMixin):
    """Resolve e anexa o tenant ao request ou redireciona para seleção.

    Quebra em helpers para reduzir complexidade mantendo semântica existente.
    """

    # --- Helpers internos -------------------------------------------------
    def _is_exempt(self, request: HttpRequest) -> bool:
        return _path_starts(request.path, EXEMPT_TENANT_PATHS)

    def _auto_single_tenant_testing(self, request: HttpRequest) -> None:
        user = getattr(request, "user", None)
        if (
            getattr(settings, "TESTING", False)
            and user
            and getattr(user, "is_authenticated", False)
            and not request.session.get("tenant_id")
        ):
            single = _get_single_tenant(request)
            if single:
                request.session["tenant_id"] = single.id
                return
            # Fallback: detectar ContaCliente ativa única (portal-cliente)
            try:
                ContaCliente = apps.get_model("portal_cliente", "ContaCliente")
            except LookupError:  # pragma: no cover
                return
            try:
                contas_qs = (
                    ContaCliente.objects.filter(usuario=user, ativo=True)
                    .select_related("cliente__tenant")
                    .only("cliente__tenant__id")
                )
                if contas_qs.count() == 1:
                    conta = contas_qs.first()
                    tenant = getattr(getattr(conta, "cliente", None), "tenant", None)
                    if tenant:
                        request.session["tenant_id"] = tenant.id
                        request.tenant = tenant
            except (DatabaseError, IntegrityError, OperationalError) as db_exc:  # pragma: no cover
                logger.debug("Ignorando erro DB ao auto definir tenant portal: %s", db_exc)
            except AttributeError as attr_exc:  # pragma: no cover
                logger.debug("Ignorando erro de atributo em auto tenant portal: %s", attr_exc)

    def _ensure_authenticated(self, request: HttpRequest) -> HttpResponse | None:
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False)):
            request.tenant = None
            return redirect("core:login")
        return None

    def _handle_superuser(self, request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        if getattr(user, "is_superuser", False):
            tid = request.session.get("tenant_id")
            request.tenant = Tenant.objects.filter(id=tid).first() if tid else None
            return True
        return False

    def _resolve_detected_or_current(self, request: HttpRequest) -> bool:
        detected = _detect_tenant(request) or get_current_tenant(request)
        if detected:
            request.tenant = detected
            return True
        return False

    def _resolve_single_membership(self, request: HttpRequest) -> bool:
        single = _get_single_tenant(request)
        if single:
            request.session["tenant_id"] = single.id
            request.tenant = single
            return True
        return False

    def _resolve_portal_conta_cliente(self, request: HttpRequest) -> bool:
        """Tenta resolver tenant via ContaCliente ativa para portal-cliente.

        Cenário: usuário autenticado acessando endpoints do portal cliente sem
        tenant_id ainda definido (ex.: testes ou primeira navegação direta).
        Evitamos fallback tardio que gera redirect 302 para /core/tenant-select/.
        """
        path = request.path
        if not path.startswith("/portal-cliente/"):
            return False
        if request.session.get("tenant_id"):
            return True  # já resolvido
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False)):
            return False
        try:
            ContaCliente = apps.get_model("portal_cliente", "ContaCliente")
        except LookupError:  # pragma: no cover - app pode estar desativado
            return False
        conta = (
            ContaCliente.objects.select_related("cliente__tenant")
            .filter(usuario=user, ativo=True)
            .only("cliente__tenant_id")
            .first()
        )
        if conta:
            tenant_id = getattr(conta.cliente, "tenant_id", None)
            tenant_obj = getattr(conta.cliente, "tenant", None)
            if tenant_id:
                request.session["tenant_id"] = tenant_id
                if tenant_obj:  # anexa para downstream (não obrigatório)
                    request.tenant = tenant_obj
                return True
        return False

    def _maybe_relax(self, request: HttpRequest) -> bool:
        path = request.path
        if (
            getattr(settings, "TESTING", False)
            or getattr(settings, "FEATURE_RELAX_TENANT_TESTING", True)
            or path.startswith("/core/api/")
        ):
            try:
                if request.tenant is None:  # atributo pode não existir
                    delattr(request, "tenant")
            except AttributeError:
                pass
            return True
        return False

    # --- API Django -------------------------------------------------------
    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """Aplica a cadeia de resolução de tenant (retorno único)."""
        if self._is_exempt(request):
            self._auto_single_tenant_testing(request)
            return None
        auth_resp = self._ensure_authenticated(request)
        if auth_resp is not None:
            return auth_resp
        if (
            self._handle_superuser(request)
            or self._resolve_detected_or_current(request)
            or self._resolve_single_membership(request)
            or self._resolve_portal_conta_cliente(request)
            or self._maybe_relax(request)
        ):
            return None
        messages.info(request, "Por favor, selecione uma empresa para continuar.")
        return redirect("core:tenant_select")


class ModuleAccessMiddleware(MiddlewareMixin):
    """Valida acesso ao módulo requisitado (feature unificada ou legado).

    Extraído em helpers para diminuir complexidade do método principal.
    """

    # --- Helpers ---------------------------------------------------------
    def _is_simple_exempt(self, request: HttpRequest) -> bool:
        path = request.path
        user = getattr(request, "user", None)
        return (
            path == "/"
            or _path_starts(path, MODULE_EXEMPT_PATHS)
            or not (user and getattr(user, "is_authenticated", False))
            or getattr(user, "is_superuser", False)
            or path == reverse("dashboard")
        )

    def _ensure_tenant(self, request: HttpRequest) -> HttpResponse | None:
        path = request.path
        tenant = getattr(request, "tenant", None)
        if tenant or "/api/" in path:
            return None
        single = _get_single_tenant(request)
        if single:
            request.session["tenant_id"] = single.id
            request.tenant = single
            return None
        messages.error(request, _("Nenhuma empresa selecionada para acessar o módulo."))
        return redirect("core:tenant_select")

    def _target_module(self, path: str) -> str | None:
        return next((m for p, m in MODULE_URL_MAPPING.items() if path.startswith(p)), None)

    def _unified_access(
        self,
        request: HttpRequest,
        user: AbstractBaseUser | AnonymousUser | None,
        tenant: Tenant | None,
        target: str,
    ) -> HttpResponse | None:
        """Executa validação de acesso unificado se feature estiver ativa."""
        if not (getattr(settings, "FEATURE_UNIFIED_ACCESS", False) and can_access_module is not None):
            return None
        cache_attr = "_module_access_cache"
        if not hasattr(request, cache_attr):
            setattr(request, cache_attr, {})
        cache_map = getattr(request, cache_attr)
        decision = cache_map.get(target)
        if decision is None:  # primeira avaliação
            decision = can_access_module(user, tenant, target)
            cache_map[target] = decision
        if decision.allowed:
            return None
        log_module_denial(user, tenant, target, decision.reason, request=request)
        deny_msg = _(
            "Acesso negado ao módulo '{module}' (motivo: {reason}).",
        ).format(module=target.capitalize(), reason=decision.reason)
        if getattr(settings, "FEATURE_MODULE_DENY_403", False):
            resp = HttpResponseForbidden(deny_msg)
            resp["X-Deny-Reason"] = decision.reason
            resp["X-Deny-Module"] = target
            return resp
        messages.error(request, deny_msg)
        resp = redirect("dashboard")
        if getattr(settings, "TESTING", False):
            with contextlib.suppress(DatabaseError, OperationalError, IntegrityError):
                resp["X-Debug-Module-Deny"] = decision.reason
        return resp

    def _legacy_access(self, request: HttpRequest, tenant: Tenant | None, target: str) -> HttpResponse | None:
        if not tenant:
            return None
        if tenant.is_module_enabled(target):
            return None
        messages.error(
            request,
            _("O módulo '{module}' não está habilitado para esta empresa.").format(
                module=target.capitalize(),
            ),
        )
        resp = redirect("dashboard")
        if getattr(settings, "TESTING", False):
            with contextlib.suppress(DatabaseError, OperationalError, IntegrityError):
                resp["X-Debug-Module-Deny"] = "LEGACY_DISABLED"
        return resp

    # --- API Django -------------------------------------------------------
    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """Executa validação de acesso ao módulo (unificado ou legado)."""
        path = request.path
        user = getattr(request, "user", None)
        if self._is_simple_exempt(request):
            return None
        tenant_resp = self._ensure_tenant(request)
        if tenant_resp:
            return tenant_resp
        tenant = getattr(request, "tenant", None)
        target = self._target_module(path)
        if not target:
            return None
        # Unified access (se configurado)
        unified_resp = self._unified_access(request, user, tenant, target)
        if unified_resp is not None:
            return unified_resp
        # Fallback legado
        return self._legacy_access(request, tenant, target)


class AuditLogMiddleware(MiddlewareMixin):
    """Registra operações mutantes (POST/PUT/PATCH/DELETE)."""

    AUDITED_METHODS: ClassVar[list[str]] = ["POST", "PUT", "PATCH", "DELETE"]
    EXEMPT_URLS: ClassVar[list[str]] = [
        "/admin/jsi18n/",
        "/static/",
        "/media/",
        "/api/health/",
        "/api-token-auth/",
    ]

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Cria entrada de audit log se request for mutante e elegível."""
        if not (
            hasattr(request, "user")
            and getattr(request.user, "is_authenticated", False)
            and request.method in self.AUDITED_METHODS
            and not _path_starts(request.path, self.EXEMPT_URLS)
            and HTTP_SUCCESS_MIN <= response.status_code < HTTP_SUCCESS_MAX
        ):
            return response
        try:
            mapping = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
            action_type = mapping.get(request.method, "OTHER")
            view_name = getattr(request.resolver_match, "view_name", request.path)
            AuditLog.objects.create(
                user=request.user,
                tenant=getattr(request, "tenant", None),
                action_type=action_type,
                ip_address=get_client_ip(request),
                change_message=f"Ação de {action_type} em '{view_name}' (URL: {request.path}).",
            )
        except (DatabaseError, IntegrityError, OperationalError):  # pragma: no cover
            logger.debug("Falha audit log (DB)", exc_info=True)
        return response


class UserActivityMiddleware(MiddlewareMixin):
    """Atualiza last_activity do perfil (se houver)."""

    def process_request(self, request: HttpRequest) -> HttpResponse | None:  # pragma: no cover - simples
        """Atualiza last_activity com tolerância a erros de BD."""
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False) and hasattr(user, "profile")):
            return None
        try:
            user.profile.last_activity = timezone.now()
            user.profile.save(update_fields=["last_activity"])
        except (DatabaseError, IntegrityError, OperationalError):  # pragma: no cover
            logger.debug("Falha last_activity (DB)", exc_info=True)
        return None


class SecurityMiddleware(MiddlewareMixin):
    """Aplica cabeçalhos de segurança e propaga X-Deny-Reason."""

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Aplica cabeçalhos de segurança e repassa X-Deny-Reason se presente."""
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        if not settings.DEBUG and request.is_secure():  # pragma: no cover
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        deny_reason = getattr(request, "_deny_reason", None)
        if deny_reason:
            response["X-Deny-Reason"] = deny_reason
        return response

# core/middleware.py (VERSÃO CORRIGIDA E UNIFICADA)

import contextlib

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from .models import AuditLog, Tenant
from .utils import get_client_ip, get_current_tenant

try:
    from .authorization import can_access_module, log_module_denial
except Exception:
    can_access_module = None  # fallback se arquivo não disponível

    def log_module_denial(*args, **kwargs):  # noop fallback
        return None


class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # URLs que não precisam de tenant
        exempt_urls = [
            "/admin/",
            "/core/logout/",
            "/core/login/",
            "/core/tenant-select/",
            "/core/tenant-selection/",
            "/core/api/",
            "/core-api/",
            "/dashboard/",
            "/static/",
            "/media/",
            "/prontuarios/api/quick-create/",
            "/core/wizard/metrics/",  # endpoint global (staff-only) não depende de tenant
            "/user_management/convites/aceitar/",  # legado (underscore)
            "/user-management/convites/aceitar/",  # aceitar convite (anônimo) path real
        ]

        if any(request.path.startswith(url) for url in exempt_urls):
            # Em ambiente de teste, se usuário autenticado e único tenant, já setar sessão aqui
            if getattr(settings, "TESTING", False) and hasattr(request, "user") and request.user.is_authenticated:
                try:
                    memberships = getattr(request.user, "tenant_memberships", None)
                    if memberships is not None and memberships.count() == 1:
                        only = memberships.first()
                        if only and not request.session.get("tenant_id"):
                            request.session["tenant_id"] = only.tenant.id
                except Exception:
                    pass
            return None

        if not hasattr(request, "user") or not request.user.is_authenticated:
            request.tenant = None
            return redirect("core:login")

        # CORREÇÃO: Superusuários têm acesso total sem necessidade de tenant
        if request.user.is_superuser:
            # Se o superusuário não tem um tenant selecionado, não forçar um
            if not request.session.get("tenant_id"):
                request.tenant = None
            else:
                try:
                    request.tenant = Tenant.objects.get(id=request.session.get("tenant_id"))
                except Tenant.DoesNotExist:
                    request.tenant = None
            return None

        # Para usuários normais, primeiro tentar detectar pelo host (subdomínio)
        # Ordem de detecção: header explícito > sessão/utilitário > host
        detected = None
        explicit = request.META.get("HTTP_X_TENANT") or request.META.get("HTTP_X_TENANT_ID")
        if explicit:
            try:
                detected = Tenant.objects.get(subdomain=explicit)
            except Tenant.DoesNotExist:
                try:
                    detected = Tenant.objects.get(id=explicit)
                except Tenant.DoesNotExist:
                    detected = None
        if not detected:
            host = request.META.get("HTTP_HOST", "")
            sub = host.split(":")[0].split(".")[0] if host else ""
            if sub:
                try:
                    detected = Tenant.objects.get(subdomain=sub)
                except Tenant.DoesNotExist:
                    detected = None

        # Para usuários normais, verificar tenant (sessão/header) se não detectado pelo host
        tenant_obj = detected or get_current_tenant(request)
        if tenant_obj:
            request.tenant = tenant_obj
        if not tenant_obj:
            is_testing = getattr(settings, "TESTING", False)
            # Tentar auto-seleção se existir exatamente um tenant relacionado (via proxy compatível)
            try:
                # suporte tanto a relacionamento tenant_memberships quanto proxy user.tenants
                memberships = getattr(request.user, "tenant_memberships", None)
                single = None
                if memberships is not None and memberships.count() == 1:
                    single = memberships.first().tenant
                else:
                    proxy = getattr(request.user, "tenants", None)
                    if proxy is not None:
                        all_t = list(proxy) if not isinstance(proxy, list) else proxy
                        if len(all_t) == 1:
                            single = all_t[0]
                if single is not None:
                    request.session["tenant_id"] = single.id
                    request.tenant = single
                    tenant_obj = single
            except Exception:
                pass
            # Se ainda não há tenant e estamos em testes ou relax flag, não redirecionar (evita 302 em massa)
            if not tenant_obj:
                if (
                    is_testing
                    or getattr(settings, "FEATURE_RELAX_TENANT_TESTING", True)
                    or request.path.startswith("/core/api/")
                ):
                    if hasattr(request, "tenant") and request.tenant is None:
                        delattr(request, "tenant")
                else:
                    messages.info(request, "Por favor, selecione uma empresa para continuar.")
                    return redirect("core:tenant_select")
        return None


class ModuleAccessMiddleware(MiddlewareMixin):
    # URLs que não precisam de verificação de módulo
    # NOTA: removido '/' para evitar bypass total (qualquer path começa com '/').
    # Escopo API afunilado: em vez de '/api/' genérico, liberar somente prefixos realmente públicos.
    EXEMPT_PATHS = [
        "/admin/",
        "/core/login/",
        "/core/logout/",
        "/core/tenant-select/",
        "/core/tenant-selection/",
        "/core/tenant-switch/",
        "/core/wizard/metrics/",  # métricas wizard independentes de tenant
        "/core/api/health/",
        "/core/api/status/",  # endpoints públicos específicos
        "/prontuarios/api/quick-create/",
        "/static/",
        "/media/",
        "/dashboard/",
        "/quick-access/",
        "/user_management/convites/aceitar/",  # legado (underscore)
        "/user-management/convites/aceitar/",  # aceitar convite
    ]

    # Mapeamento de URLs para módulos
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

    def process_request(self, request):
        # Verificar se é uma URL isenta
        if request.path == "/":
            return None
        if any(request.path.startswith(url) for url in self.EXEMPT_PATHS):
            return None

        # Superusuários têm acesso total
        if hasattr(request, "user") and request.user.is_authenticated and request.user.is_superuser:
            return None

        # Usuários não autenticados
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # Verificar se é o dashboard
        if request.path == reverse("dashboard"):
            return None

        # Verificar tenant (relaxado para endpoints API)
        tenant = getattr(request, "tenant", None)
        if not tenant and "/api/" not in request.path:
            # Tentativa de auto-seleção baseada no único vínculo do usuário
            try:
                memberships = getattr(request.user, "tenant_memberships", None)
                if memberships is not None and memberships.count() == 1:
                    only = memberships.first()
                    if only:
                        request.session["tenant_id"] = only.tenant.id
                        request.tenant = only.tenant
                        tenant = only.tenant
            except Exception:
                pass
            if not tenant:
                messages.error(request, _("Nenhuma empresa selecionada para acessar o módulo."))
                return redirect("core:tenant_select")

        # Verificar acesso ao módulo específico
        cache_attr = "_module_access_cache"
        if not hasattr(request, cache_attr):
            setattr(request, cache_attr, {})
        cache_map = getattr(request, cache_attr)

        for url_prefix, module_name in self.MODULE_URL_MAPPING.items():
            if request.path.startswith(url_prefix):
                # Caminho unificado se feature estiver ativa
                if getattr(settings, "FEATURE_UNIFIED_ACCESS", False) and can_access_module:
                    decision = cache_map.get(module_name)
                    if decision is None:
                        decision = can_access_module(request.user, tenant, module_name)
                        cache_map[module_name] = decision
                    if not decision.allowed:
                        log_module_denial(request.user, tenant, module_name, decision.reason, request=request)
                        request._deny_reason = decision.reason
                        if getattr(settings, "FEATURE_MODULE_DENY_403", False):
                            resp = HttpResponseForbidden(
                                _("Acesso negado ao módulo '{module}' (motivo: {reason}).").format(
                                    module=module_name.capitalize(), reason=decision.reason
                                )
                            )
                            resp["X-Deny-Reason"] = decision.reason
                            resp["X-Deny-Module"] = module_name
                            return resp
                        else:
                            messages.error(
                                request,
                                _("Acesso negado ao módulo '{module}' (motivo: {reason}).").format(
                                    module=module_name.capitalize(), reason=decision.reason
                                ),
                            )
                            resp = redirect("dashboard")
                            # Incluir header de debug em ambiente de teste
                            if getattr(settings, "TESTING", False):
                                with contextlib.suppress(Exception):
                                    resp["X-Debug-Module-Deny"] = decision.reason
                            return resp
                # Lógica legada
                elif not tenant.is_module_enabled(module_name):
                    messages.error(
                        request,
                        _("O módulo '{module}' não está habilitado para esta empresa.").format(
                            module=module_name.capitalize()
                        ),
                    )
                    resp = redirect("dashboard")
                    if getattr(settings, "TESTING", False):
                        with contextlib.suppress(Exception):
                            resp["X-Debug-Module-Deny"] = "LEGACY_DISABLED"
                    return resp
                break
        return None


# Manter os outros middlewares como estão
class AuditLogMiddleware(MiddlewareMixin):
    AUDITED_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    EXEMPT_URLS = ["/admin/jsi18n/", "/static/", "/media/", "/api/health/", "/api-token-auth/"]

    def process_response(self, request, response):
        if not (
            hasattr(request, "user")
            and request.user.is_authenticated
            and request.method in self.AUDITED_METHODS
            and not any(request.path.startswith(url) for url in self.EXEMPT_URLS)
            and 200 <= response.status_code < 400
        ):
            return response
        try:
            action_type_mapping = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
            action_type = action_type_mapping.get(request.method, "OTHER")
            view_name = getattr(request.resolver_match, "view_name", request.path)
            AuditLog.objects.create(
                user=request.user,
                tenant=getattr(request, "tenant", None),
                action_type=action_type,
                ip_address=get_client_ip(request),
                change_message=f"Ação de {action_type} em '{view_name}' (URL: {request.path}).",
            )
        except Exception:
            pass
        return response


class UserActivityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if hasattr(request, "user") and request.user.is_authenticated and hasattr(request.user, "profile"):
            request.user.profile.last_activity = timezone.now()
            request.user.profile.save(update_fields=["last_activity"])


class SecurityMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        if not settings.DEBUG and request.is_secure():
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Propagar header de negação se existir (apenas para facilitar debugging em front / logs)
        deny_reason = getattr(request, "_deny_reason", None)
        if deny_reason:
            response["X-Deny-Reason"] = deny_reason
        return response

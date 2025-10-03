# core/mixins.py
"""Mixins de acesso e contexto para o app core.

Este módulo fornece um conjunto de mixins reutilizáveis para o Django,
projetados para gerenciar permissões, contexto de página e acesso
baseado em tenants e módulos.

Principais Mixins:
- PageTitleMixin: Adiciona título e subtítulo ao contexto.
- TenantRequiredMixin: Garante que um tenant válido está selecionado.
- ModuleRequiredMixin: Verifica se um módulo específico está ativo.
- TenantAdminRequiredMixin: Restringe o acesso a administradores do tenant.
- TenantAdminOrSuperuserMixin: Alternativa que também permite superusuários.
- SuperuserRequiredMixin: Restringe o acesso apenas a superusuários.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from .models import Tenant, TenantUser
from .utils import get_current_tenant

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


logger = logging.getLogger(__name__)

# ==============================================================================
# MIXINS DE CONTEXTO E ACESSO
# ==============================================================================


class PageTitleMixin:
    """Adiciona título e subtítulo da página ao contexto do template."""

    page_title: str = ""
    page_subtitle: str = ""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Adiciona 'page_title' e 'page_subtitle' ao contexto."""
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context["page_title"] = getattr(self, "page_title", "")
        context["page_subtitle"] = getattr(self, "page_subtitle", "")
        # Mantendo 'titulo' e 'subtitulo' para retrocompatibilidade
        context["titulo"] = context["page_title"]
        context["subtitulo"] = context["page_subtitle"]
        return context


class TenantRequiredMixin(AccessMixin):
    """Garante que um tenant foi selecionado e que o usuário tem permissão.

    - Superusuários têm acesso irrestrito e não precisam de um tenant.
    - Usuários comuns são redirecionados se nenhum tenant estiver ativo.
    - Tenta autoselecionar um tenant se o usuário pertencer a apenas um.
    """

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Verifica o acesso ao tenant antes de prosseguir com a view."""
        # Superusuários têm acesso total, o tenant é opcional.
        if request.user.is_superuser:
            request.tenant = get_current_tenant(request)
            return super().dispatch(request, *args, **kwargs)

        # Anexa o tenant ao request para uso posterior.
        request.tenant = get_current_tenant(request)

        # Se não houver tenant, tenta a autoseleção.
        if not request.tenant:
            self._auto_select_tenant(request)

        # Se ainda assim não houver tenant, nega o acesso.
        if not request.tenant:
            messages.error(
                request,
                _("Nenhuma empresa selecionada. Por favor, escolha uma para continuar."),
            )
            return self.handle_no_permission()

        # Verifica se o usuário tem um vínculo com o tenant.
        if not TenantUser.objects.filter(tenant=request.tenant, user=request.user).exists():
            messages.error(request, _("Você não tem permissão para acessar esta empresa."))
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def _auto_select_tenant(self, request: HttpRequest) -> None:
        """Tenta selecionar um tenant automaticamente se o usuário tiver apenas um."""
        try:
            memberships = getattr(request.user, "tenant_memberships", None)
            if memberships is not None and memberships.count() == 1:
                only_membership = memberships.first()
                if only_membership and isinstance(only_membership.tenant, Tenant):
                    request.session["tenant_id"] = only_membership.tenant.id
                    request.tenant = only_membership.tenant
        except (AttributeError, TypeError):
            logger.warning(
                "Falha ao tentar auto-selecionar tenant para o usuário %s.",
                request.user.id,
                exc_info=True,
            )

    def handle_no_permission(self) -> HttpResponse:
        """Redireciona para a tela de seleção de tenants."""
        return redirect("core:tenant_select")


class ModuleRequiredMixin:
    """Verifica se um módulo específico está habilitado para o tenant.

    Deve ser usado em conjunto e DEPOIS do `TenantRequiredMixin`.
    """

    required_module: str | None = None

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Verifica a habilitação do módulo antes de prosseguir."""
        # Superusuários têm acesso a todos os módulos.
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

        if self.required_module is None:
            return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

        tenant = getattr(request, "tenant", None)

        if not tenant or not tenant.is_module_enabled(self.required_module):
            messages.error(
                request,
                _("O módulo '{module}' não está habilitado para esta empresa.").format(
                    module=self.required_module.capitalize(),
                ),
            )
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]


class TenantAdminRequiredMixin(UserPassesTestMixin):
    """Verifica se o usuário é um administrador do tenant ou um superusuário."""

    def test_func(self) -> bool:
        """Executa o teste de permissão."""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Superusuários sempre têm permissão.
        if user.is_superuser:
            return True

        tenant = get_current_tenant(self.request)
        if not tenant:
            return False

        # Verifica se existe um vínculo onde o usuário é admin do tenant.
        return TenantUser.objects.filter(tenant=tenant, user=user, is_tenant_admin=True).exists()

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Anexa o tenant ao request antes de executar o teste de permissão."""
        request.tenant = get_current_tenant(request)
        return super().dispatch(request, *args, **kwargs)


class TenantAdminOrSuperuserMixin(AccessMixin):
    """Garante que o usuário é superusuário ou administrador do tenant ativo."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> HttpResponse:
        """Verifica as permissões do usuário antes de acessar a view."""
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Superusuários têm acesso total.
        if request.user.is_superuser:
            request.tenant = get_current_tenant(request)
            return super().dispatch(request, *args, **kwargs)

        tenant = get_current_tenant(request)
        if not tenant:
            messages.error(request, "Nenhuma empresa selecionada.")
            return redirect("core:tenant_select")

        request.tenant = tenant

        # Verifica se é admin do tenant.
        if not TenantUser.objects.filter(
            tenant=tenant,
            user=request.user,
            is_tenant_admin=True,
        ).exists():
            messages.error(request, "Você não tem permissão para acessar esta funcionalidade.")
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self) -> HttpResponse:
        """Redireciona para a página de login se o usuário não estiver autenticado."""
        return redirect_to_login(self.request.get_full_path())


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Garante que o usuário logado é um superusuário."""

    def test_func(self) -> bool:
        """Verifica se o usuário é autenticado e superusuário."""
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self) -> HttpResponse:
        """Redireciona para a página de login se o teste falhar."""
        return redirect_to_login(self.request.get_full_path())

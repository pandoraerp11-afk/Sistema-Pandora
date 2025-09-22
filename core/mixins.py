# core/mixins.py (Versão Corrigida - Superusuários têm acesso total)

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

# Importando o modelo e a função utilitária que vamos usar.
from .models import TenantUser
from .utils import get_current_tenant

# ==============================================================================
# MIXINS DE CONTEXTO E ACESSO
# ==============================================================================


class PageTitleMixin:
    """
    Mixin genérico para adicionar título e subtítulo da página ao contexto do template.
    """

    page_title = ""
    page_subtitle = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = getattr(self, "page_title", "")
        context["page_subtitle"] = getattr(self, "page_subtitle", "")
        # Mantendo 'titulo' e 'subtitulo' para retrocompatibilidade com seus templates
        context["titulo"] = context["page_title"]
        context["subtitulo"] = context["page_subtitle"]
        return context


class TenantRequiredMixin(AccessMixin):
    """
    Garante que um tenant (empresa) foi selecionado e que o usuário logado
    tem permissão para acessá-lo.

    CORREÇÃO: Superusuários têm acesso total sem precisar de empresa selecionada.
    """

    def dispatch(self, request, *args, **kwargs):
        # CORREÇÃO: Superusuários têm acesso total, não precisam de tenant obrigatório
        if request.user.is_superuser:
            # Para superusuários, tentamos pegar o tenant da sessão, mas não é obrigatório
            request.tenant = get_current_tenant(request)
            return super().dispatch(request, *args, **kwargs)

        # 1. Anexa o objeto tenant ao request para ser reutilizado por outros mixins e views.
        request.tenant = get_current_tenant(request)

        # 2. Se nenhum tenant foi encontrado na sessão, redireciona para a tela de seleção.
        if not request.tenant:
            # Auto seleção se usuário tiver exatamente um vínculo
            try:
                memberships = getattr(request.user, "tenant_memberships", None)
                if memberships is not None and memberships.count() == 1:
                    only = memberships.first()
                    if only:
                        request.session["tenant_id"] = only.tenant.id
                        request.tenant = only.tenant
            except Exception:
                pass
            if not request.tenant:
                messages.error(request, _("Nenhuma empresa selecionada. Por favor, escolha uma para continuar."))
                return self.handle_no_permission()

        # 3. Verifica se o usuário tem um vínculo com o tenant.
        has_access = TenantUser.objects.filter(tenant=request.tenant, user=request.user).exists()
        if not has_access:
            messages.error(request, _("Você não tem permissão para acessar esta empresa."))
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        # Redireciona para a tela de seleção de tenants se a verificação falhar.
        return redirect("core:tenant_select")


class ModuleRequiredMixin:
    """
    Mixin para verificar se um módulo específico está habilitado para o tenant atual.
    Deve ser usado DEPOIS do TenantRequiredMixin.
    """

    required_module = None  # Defina este atributo na sua View. Ex: required_module = 'financeiro'

    def dispatch(self, request, *args, **kwargs):
        # CORREÇÃO: Superusuários têm acesso a todos os módulos
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        if self.required_module is None:
            # Se nenhum módulo for exigido, apenas continua.
            return super().dispatch(request, *args, **kwargs)

        # O tenant já foi anexado ao request pelo TenantRequiredMixin.
        tenant = getattr(request, "tenant", None)

        if not tenant or not tenant.is_module_enabled(self.required_module):
            messages.error(
                request,
                _("O módulo '{module}' não está habilitado para esta empresa.").format(
                    module=self.required_module.capitalize()
                ),
            )
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)


class TenantAdminRequiredMixin(UserPassesTestMixin):
    """
    Mixin para verificar se o usuário é um administrador do tenant atual (ou superuser).
    CORREÇÃO: Superusuários têm acesso total, mesmo sem tenant.
    """

    def test_func(self):
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Superusuários sempre têm permissão.
        if user.is_superuser:
            return True

        # Para outros usuários, verifica se tem tenant e se é admin
        tenant = get_current_tenant(self.request)
        if not tenant:
            return False

        # Verifica se existe um vínculo onde o usuário é marcado como admin do tenant.
        return TenantUser.objects.filter(tenant=tenant, user=user, is_tenant_admin=True).exists()

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch para anexar tenant ao request quando necessário"""
        # Anexa tenant ao request para uso nas views
        request.tenant = get_current_tenant(request)
        return super().dispatch(request, *args, **kwargs)


class TenantAdminOrSuperuserMixin:
    """
    Mixin alternativo que garante que superusuários tenham acesso total
    e outros usuários precisem ser admin do tenant.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Superusuários têm acesso total
        if request.user.is_superuser:
            request.tenant = get_current_tenant(request)  # Pode ser None, mas não impede o acesso
            return super().dispatch(request, *args, **kwargs)
        # Para outros usuários, verificar tenant e permissão
        tenant = get_current_tenant(request)
        if not tenant:
            messages.error(request, "Nenhuma empresa selecionada.")
            return redirect("core:tenant_select")

        request.tenant = tenant

        # Verificar se é admin do tenant
        if not TenantUser.objects.filter(tenant=tenant, user=request.user, is_tenant_admin=True).exists():
            messages.error(request, "Você não tem permissão para acessar esta funcionalidade.")
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(self.request.get_full_path())


class SuperuserRequiredMixin(UserPassesTestMixin):
    """
    Mixin para verificar se o usuário é superusuário.
    Para funcionalidades administrativas globais.
    """

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):  # Redirecionar para login ao invés de 403 para alinhar com testes
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(self.request.get_full_path())

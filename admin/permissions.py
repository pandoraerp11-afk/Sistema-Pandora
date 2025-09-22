# admin/permissions.py

from rest_framework import permissions

from core.models import TenantUser


class IsSystemAdmin(permissions.BasePermission):
    """
    Permissão customizada que permite acesso apenas a superusuários do Django.
    Útil para os endpoints do painel de controle geral do sistema.
    """

    def has_permission(self, request, view):
        # A verificação é simples: o usuário deve estar autenticado e ser um superusuário.
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsTenantAdmin(permissions.BasePermission):
    """
    Permissão que verifica se o usuário é administrador do tenant
    cujo `pk` ou `id` está na URL.
    Ex: /api/tenants/123/users/ -> Verifica se o usuário é admin do tenant 123.
    """

    def has_permission(self, request, view):
        # Superusuários sempre têm permissão.
        if request.user and request.user.is_authenticated and request.user.is_superuser:
            return True

        # Pega o ID do tenant da URL (kwargs são os parâmetros da URL, como o 'pk')
        tenant_pk = view.kwargs.get("tenant_pk") or view.kwargs.get("pk")
        if not tenant_pk:
            # Se a URL não tem um ID de tenant, esta permissão não se aplica.
            return False

        # Verifica se existe um vínculo de TenantUser onde o usuário é admin para aquele tenant específico.
        return TenantUser.objects.filter(tenant_id=tenant_pk, user=request.user, is_tenant_admin=True).exists()


class IsTenantAdminOrSystemAdminForObject(permissions.BasePermission):
    """
    Permissão de objeto que verifica se o usuário é:
    1. Um superusuário do sistema.
    2. OU um administrador do tenant ao qual o objeto pertence.
    """

    def has_object_permission(self, request, view, obj):
        # Superusuários sempre têm permissão.
        if request.user and request.user.is_authenticated and request.user.is_superuser:
            return True

        # O objeto 'obj' que está sendo acessado (ex: um Alerta, uma Métrica)
        # deve ter um campo chamado 'tenant'.
        if not hasattr(obj, "tenant"):
            # Se o objeto não pertence a um tenant, nega o acesso por segurança.
            return False

        # Verifica se o usuário é admin do tenant ao qual o objeto pertence.
        return TenantUser.objects.filter(tenant=obj.tenant, user=request.user, is_tenant_admin=True).exists()

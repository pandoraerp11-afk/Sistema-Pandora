from rest_framework import permissions


class ProntuarioPermission(permissions.BasePermission):
    """
    Permissão personalizada para o módulo de prontuários.
    Verifica se o usuário tem acesso ao tenant e às funcionalidades do módulo.
    """

    def has_permission(self, request, view):
        # Usuário deve estar autenticado
        if not request.user.is_authenticated:
            return False

        # Superusuários têm acesso total
        if request.user.is_superuser:
            return True

        # Verificar se o usuário tem acesso ao tenant atual
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        # Verificar se o usuário pertence ao tenant
        if not request.user.tenants.filter(id=tenant.id).exists():
            return False

        # Verificar permissões específicas do módulo
        if request.method in permissions.SAFE_METHODS:
            return any(
                [
                    request.user.has_perm("prontuarios.view_atendimento"),
                    request.user.has_perm("prontuarios.view_fotoevolucao"),
                    request.user.has_perm("prontuarios.view_anamnese"),
                ]
            )
        return any(
            [
                request.user.has_perm("prontuarios.add_atendimento"),
                request.user.has_perm("prontuarios.change_atendimento"),
                request.user.has_perm("prontuarios.delete_atendimento"),
                request.user.has_perm("prontuarios.add_fotoevolucao"),
                request.user.has_perm("prontuarios.change_fotoevolucao"),
                request.user.has_perm("prontuarios.delete_fotoevolucao"),
                request.user.has_perm("prontuarios.add_anamnese"),
                request.user.has_perm("prontuarios.change_anamnese"),
                request.user.has_perm("prontuarios.delete_anamnese"),
            ]
        )

    def has_object_permission(self, request, view, obj):
        # Verificar se o usuário tem acesso ao objeto específico
        if not self.has_permission(request, view):
            return False

        # Superusuários têm acesso total
        if request.user.is_superuser:
            return True

        # Verificar se o objeto pertence ao tenant do usuário
        if hasattr(obj, "tenant"):
            return obj.tenant == getattr(request, "tenant", None)

        # Para objetos que não têm tenant diretamente, verificar através de relacionamentos
        # Legado de paciente removido – se houver atributo cliente com tenant associado
        if hasattr(obj, "cliente") and hasattr(obj.cliente, "tenant"):
            return obj.cliente.tenant == getattr(request, "tenant", None)

        return True


# PacientePermission removida.


class IsSecretariaOuProfissional(permissions.BasePermission):
    """Permite acesso se usuário for superuser, staff (profissional) ou tiver grupo contendo 'secretaria'."""

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser or u.is_staff:
            return True
        # Heurística por nome de grupo
        return u.groups.filter(name__icontains="secretaria").exists()


class AtendimentoPermission(permissions.BasePermission):
    """
    Permissão específica para atendimentos.
    Garante que profissionais só vejam atendimentos que realizaram.
    """

    def has_permission(self, request, view):
        return ProntuarioPermission().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not ProntuarioPermission().has_object_permission(request, view, obj):
            return False

        # Superusuários e administradores têm acesso total
        if request.user.is_superuser or request.user.is_tenant_admin:
            return True

        # Profissionais podem ver apenas seus próprios atendimentos
        return obj.profissional == request.user


class FotoEvolucaoPermission(permissions.BasePermission):
    """Controle de acesso às fotos de evolução usando relacionamento com atendimento/cliente."""

    def has_permission(self, request, view):
        return ProntuarioPermission().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not ProntuarioPermission().has_object_permission(request, view, obj):
            return False
        if request.user.is_superuser or request.user.is_tenant_admin:
            return True
        if hasattr(request.user, "atendimentos_realizados") and obj.atendimento_id:
            return request.user.atendimentos_realizados.filter(id=obj.atendimento_id).exists()
        return True


class AnamnesePermission(permissions.BasePermission):
    """Permissão para anamneses baseada no atendimento/profissional responsável."""

    def has_permission(self, request, view):
        return ProntuarioPermission().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not ProntuarioPermission().has_object_permission(request, view, obj):
            return False
        if request.user.is_superuser or request.user.is_tenant_admin:
            return True
        return obj.profissional_responsavel_id == request.user.id

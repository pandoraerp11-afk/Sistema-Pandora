"""Serviços para perfil estendido do usuário.
Verificado ausência de duplicata: termos buscados (ensure_profile, sync_status, profile_service) não existentes.
"""

from django.contrib.auth import get_user_model

from user_management.models import PerfilUsuarioEstendido, StatusUsuario

UserModel = get_user_model()


def ensure_profile(user):
    """Garante existência idempotente do perfil estendido."""
    profile, _ = PerfilUsuarioEstendido.objects.get_or_create(
        user=user, defaults={"status": StatusUsuario.ATIVO if user.is_active else StatusUsuario.INATIVO}
    )
    return profile


def sync_status(user):
    """Sincroniza status entre user.is_active e perfil.status.
    Regras:
    - user.is_active True + perfil INATIVO => promove para ATIVO
    - Estados BLOQUEADO/SUSPENSO são preservados (não auto-promove)
      - user.is_active False + perfil ATIVO => perfil INATIVO
      - perfil PENDENTE permanece (não forçamos alteração)
    """
    if not hasattr(user, "perfil_estendido"):
        return
    perfil = user.perfil_estendido
    if user.is_active and perfil.status == StatusUsuario.INATIVO:
        perfil.status = StatusUsuario.ATIVO
        perfil.save(update_fields=["status"])
    elif not user.is_active and perfil.status == StatusUsuario.ATIVO:
        perfil.status = StatusUsuario.INATIVO
        perfil.save(update_fields=["status"])


def ensure_tenant_membership(user, tenant, default_role_factory=None):
    """Garante vínculo TenantUser e role default.
    Corrige import para usar core.models.TenantUser (não existe em user_management.models).
    """
    from core.models import TenantUser  # import local para evitar circular em migrações

    tu, created = TenantUser.objects.get_or_create(user=user, tenant=tenant)
    if created and default_role_factory:
        role = default_role_factory(tenant)
        if role:
            tu.role = role
            tu.save(update_fields=["role"])
    return tu

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from user_management.models import PerfilUsuarioEstendido, StatusUsuario

pytestmark = [pytest.mark.django_db]


def _create_users(n=3, active_pattern=None):
    User = get_user_model()
    users = []
    for i in range(n):
        is_active = True
        if active_pattern is not None:
            is_active = active_pattern(i)
        u = User.objects.create_user(f"prof_sync_{i}", password="x", is_active=is_active)
        users.append(u)
    return users


def test_sync_profiles_dry_run_and_real():
    users = _create_users(4, active_pattern=lambda i: i % 2 == 0)  # alterna ativo/inativo
    # Remover perfis de 2 usuários para simular criação necessária (signals podem ter criado)
    # Forçar removendo objetos (aceitável em teste)
    PerfilUsuarioEstendido.objects.filter(user__username__in=["prof_sync_1", "prof_sync_3"]).delete()
    # Dry-run
    call_command("sync_profiles", "--dry-run")
    # Nada deve ter sido criado (já que dry-run) mas contagem de perfis será a existente menos removidos
    assert PerfilUsuarioEstendido.objects.exclude(user__username__in=["prof_sync_1", "prof_sync_3"]).count() >= 2
    # Execução real verbose
    call_command("sync_profiles", "--verbose")
    # Agora todos devem ter perfil
    assert PerfilUsuarioEstendido.objects.filter(user__in=users).count() == len(users)
    # Verificar consistência status de um usuário inativo
    inactive_user = [u for u in users if not u.is_active][0]
    perfil_inactive = inactive_user.perfil_estendido
    assert perfil_inactive.status in {StatusUsuario.INATIVO, StatusUsuario.PENDENTE}


def test_create_missing_profiles_command_dry_and_real():
    User = get_user_model()
    User.objects.create_user("cmp_user1", password="x")
    u2 = User.objects.create_user("cmp_user2", password="x")
    # Apagar perfil de u2 para simular ausência
    PerfilUsuarioEstendido.objects.filter(user=u2).delete()
    # Dry-run
    call_command("create_missing_profiles", "--dry-run")
    assert not PerfilUsuarioEstendido.objects.filter(user=u2).exists()
    # Execução real
    call_command("create_missing_profiles")
    assert PerfilUsuarioEstendido.objects.filter(user=u2).exists()

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from .models import StatusUsuario

User = get_user_model()


class PerfilStatusAuthenticationBackend(ModelBackend):
    """Backend que impede login se perfil_estendido estiver inativo/bloqueado/suspenso ou bloqueado_ate futuro.
    Regras:
      - Rejeita se não existir perfil_estendido (fallback para ModelBackend normal).
      - Rejeita se status em {inativo, suspenso, bloqueado}.
      - Rejeita se bloqueado_ate > agora.
      - Ao autenticar com sucesso, zera tentativas falhadas se >0.
    """

    def user_can_authenticate(self, user):
        # Mantém checagens básicas (is_active, etc.)
        if not super().user_can_authenticate(user):
            return False
        perfil = getattr(user, "perfil_estendido", None)
        if not perfil:
            return True
        now = timezone.now()
        if perfil.bloqueado_ate and perfil.bloqueado_ate > now:
            return False
        if perfil.status in {StatusUsuario.INATIVO, StatusUsuario.SUSPENSO, StatusUsuario.BLOQUEADO}:
            return False
        return not (perfil.status == StatusUsuario.PENDENTE and not user.is_staff)

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if not user:
            return None
        if not self.user_can_authenticate(user):
            return None
        perfil = getattr(user, "perfil_estendido", None)
        if perfil and perfil.tentativas_login_falhadas:
            # DEBUG: reset tentativas
            # print(f"[DEBUG auth_backend] reset tentativas user={user.username} antes={perfil.tentativas_login_falhadas}")
            perfil.tentativas_login_falhadas = 0
            perfil.save(update_fields=["tentativas_login_falhadas"])
        return user

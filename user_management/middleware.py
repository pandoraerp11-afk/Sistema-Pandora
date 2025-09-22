"""Middleware simples para anexar perfil estendido ao request como request.user_profile.
Idempotente e barato; evita múltiplos acessos a atributo O2O em views.
"""

from django.utils.deprecation import MiddlewareMixin


class UserProfileAttachMiddleware(MiddlewareMixin):
    def process_request(self, request):  # pragma: no cover (uso simples)
        u = getattr(request, "user", None)
        if u and u.is_authenticated and not hasattr(request, "user_profile"):
            perfil = getattr(u, "perfil_estendido", None)
            if perfil:
                request.user_profile = perfil

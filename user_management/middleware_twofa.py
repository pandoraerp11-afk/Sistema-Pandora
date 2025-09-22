from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

EXEMPT_PATHS = {
    "/admin/login/",
}


class TwoFAMiddleware(MiddlewareMixin):
    """Exige verificação 2FA se usuário tiver 2FA habilitado e confirmado.
    Armazena na sessão flag 'twofa_passed'.
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        path = request.path
        if path.startswith("/static/") or path.startswith("/media/"):
            return None
        if path.startswith("/user-management/2fa"):
            return None
        if path in EXEMPT_PATHS:
            return None
        perfil = getattr(request.user, "perfil_estendido", None)
        if not perfil or not perfil.autenticacao_dois_fatores or not perfil.totp_secret:
            return None
        # Se ainda não confirmado (setup em andamento) deixa acessar confirm endpoints
        if not perfil.totp_confirmed_at:
            return None
        if request.session.get("twofa_passed"):
            return None
        # Redireciona para challenge
        challenge_url = reverse("user_management:2fa_challenge")
        if path != challenge_url:
            return redirect(challenge_url)
        return None

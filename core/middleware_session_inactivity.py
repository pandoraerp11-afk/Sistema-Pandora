from django.conf import settings
from django.utils import timezone

from user_management.models import SessaoUsuario


class SessionInactivityMiddleware:
    """Marca SessaoUsuario como inativa se exceder SESSION_MAX_INACTIVITY_MINUTES.
    Deve ser adicionada após middleware de autenticação.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_delta = getattr(settings, "SESSION_MAX_INACTIVITY_MINUTES", 120)

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if request.user.is_authenticated and request.session.session_key:
                sess = SessaoUsuario.objects.filter(session_key=request.session.session_key, ativa=True).first()
                if sess:
                    now = timezone.now()
                    delta = (now - (sess.ultima_atividade or sess.created_at)).total_seconds() / 60.0
                    if delta > self.max_delta:
                        sess.ativa = False
                        sess.save(update_fields=["ativa"])
                    else:
                        # Atualiza ultima_atividade para prolongar
                        sess.ultima_atividade = now
                        sess.save(update_fields=["ultima_atividade"])
        except Exception:
            pass
        return response

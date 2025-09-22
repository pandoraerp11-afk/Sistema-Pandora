import uuid

from django.utils.deprecation import MiddlewareMixin


class PortalRequestIDMiddleware(MiddlewareMixin):
    """Anexa um X-Portal-Request-ID a cada request do portal cliente para correlação de logs.
    Só ativa para paths que começam com /portal-cliente/.
    """

    HEADER = "HTTP_X_PORTAL_REQUEST_ID"
    RESPONSE_HEADER = "X-Portal-Request-ID"

    def process_request(self, request):
        if request.path.startswith("/portal-cliente/"):
            rid = request.META.get(self.HEADER)
            if not rid:
                rid = uuid.uuid4().hex[:16]
            request.portal_request_id = rid

    def process_response(self, request, response):
        rid = getattr(request, "portal_request_id", None)
        if rid:
            response[self.RESPONSE_HEADER] = rid
        return response

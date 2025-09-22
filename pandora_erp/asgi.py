"""
ASGI config for pandora_erp project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora_erp.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

import core.routing

try:
    import user_management.routing

    _sessions_patterns = getattr(user_management.routing, "websocket_urlpatterns", [])
except Exception:
    _sessions_patterns = []
try:
    import chat.routing

    _chat_patterns = getattr(chat.routing, "websocket_urlpatterns", [])
except Exception:
    _chat_patterns = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(core.routing.websocket_urlpatterns + _chat_patterns + _sessions_patterns))
        ),
    }
)

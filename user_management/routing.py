from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/sessions/$", consumers.SessionsConsumer.as_asgi()),
]

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/conversa/(?P<conversa_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/chat/overview/$", consumers.ChatOverviewConsumer.as_asgi()),
]

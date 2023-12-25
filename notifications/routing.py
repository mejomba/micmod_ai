from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/notifications/<str:user_id>/', consumers.MessagesConsumer.as_asgi()),
    # path('ws/videochat/', consumers.VideoChatConsumer)
]
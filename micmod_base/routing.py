from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/micmod_base/quotationitem/list/form/pending/', consumers.QuotationItemConsumer.as_asgi()),
    # path('ws/videochat/', consumers.VideoChatConsumer)
]
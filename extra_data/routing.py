# your_app/routing.py (نام اپ خود را جایگزین کنید - مثلا forms یا همان اپ اصلی)
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/form/<int:form_id>/', consumers.FormConsumer.as_asgi()),
]
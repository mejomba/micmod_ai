"""
ASGI config for _keenthemes project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.sessions import SessionMiddlewareStack
from django.core.asgi import get_asgi_application
from notifications import routing as notifications_routing
from extra_data import routing as extra_data_routing

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_keenthemes.settings')

# application = get_asgi_application()


django_asgi_app = get_asgi_application()

# application = ProtocolTypeRouter({
#     "http": django_asgi_app,
#     # Just HTTP for now. (We can add other protocols later.)
# })

combined_websocket_urlpatterns = (
    notifications_routing.websocket_urlpatterns +
    extra_data_routing.websocket_urlpatterns  # اضافه کردن routing فرم
)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        SessionMiddlewareStack(
            AuthMiddlewareStack(
                URLRouter(
                    combined_websocket_urlpatterns
                    # notifications_routing.websocket_urlpatterns
                    #+ chat_routing.websocket_urlpatterns
                )
            )
        )
    )
})
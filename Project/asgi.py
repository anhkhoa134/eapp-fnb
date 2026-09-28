"""
ASGI config for Project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Project.settings')

django_asgi_application = get_asgi_application()

from Project.routing import websocket_urlpatterns  # noqa: E402


application = ProtocolTypeRouter(
    {
        'http': django_asgi_application,
        # Chỉ nhận WebSocket mở từ trang cùng domain (ALLOWED_HOSTS): chặn trang lạ dùng cookie phiên của nhân viên.
        'websocket': AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(websocket_urlpatterns))),
    }
)

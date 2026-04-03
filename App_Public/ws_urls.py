from django.urls import re_path

from App_Public.consumers import PublicQROrderConsumer

websocket_urlpatterns = [
    re_path(r'^ws/public/qr/order/(?P<order_id>\d+)/$', PublicQROrderConsumer.as_asgi()),
]

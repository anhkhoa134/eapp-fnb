from django.urls import re_path

from App_Sales.consumers import PosStoreConsumer

websocket_urlpatterns = [
    re_path(r'^ws/pos/store/(?P<store_id>\d+)/$', PosStoreConsumer.as_asgi()),
]

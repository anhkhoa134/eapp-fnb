from App_Public.ws_urls import websocket_urlpatterns as public_websocket_urlpatterns
from App_Sales.ws_urls import websocket_urlpatterns as sales_websocket_urlpatterns

websocket_urlpatterns = [
    *sales_websocket_urlpatterns,
    *public_websocket_urlpatterns,
]

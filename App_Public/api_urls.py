from django.urls import path

from App_Public import views

app_name = 'App_Public_API'

urlpatterns = [
    path('qr/orders/', views.api_public_qr_orders, name='qr_orders_create'),
    path('qr/orders/<int:order_id>/', views.api_public_qr_order_detail, name='qr_orders_detail'),
    path('qr/orders/<int:order_id>/cancel/', views.api_public_qr_order_cancel, name='qr_orders_cancel'),
]

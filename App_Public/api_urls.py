from django.urls import path

from App_Public import views

app_name = 'App_Public_API'

urlpatterns = [
    path('qr/orders/', views.api_public_qr_orders, name='qr_orders_create'),
]

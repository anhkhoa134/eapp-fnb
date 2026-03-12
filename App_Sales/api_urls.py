from django.urls import path

from App_Sales import views

app_name = 'App_Sales_API'

urlpatterns = [
    path('products/', views.api_products, name='products'),
    path('checkout/', views.api_checkout, name='checkout'),
]

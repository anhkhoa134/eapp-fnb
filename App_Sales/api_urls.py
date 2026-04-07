from django.urls import path

from App_Sales import views

app_name = 'App_Sales_API'

urlpatterns = [
    path('products/', views.api_products, name='products'),
    path('checkout/', views.api_checkout, name='checkout'),
    path('tables/', views.api_tables, name='tables'),
    path('tables/<int:table_id>/cart/', views.api_table_cart, name='table_cart'),
    path('tables/<int:table_id>/cart/items/', views.api_table_cart_add, name='table_cart_add'),
    path('tables/<int:table_id>/cart/import-takeaway/', views.api_table_import_takeaway, name='table_import_takeaway'),
    path('tables/<int:table_id>/cart/move-to/', views.api_table_cart_move_to, name='table_cart_move_to'),
    path('tables/<int:table_id>/cart/items/<int:item_id>/', views.api_table_cart_item, name='table_cart_item'),
    path('tables/<int:table_id>/checkout/', views.api_table_checkout, name='table_checkout'),
    path('qr/orders/', views.api_qr_orders, name='qr_orders'),
    path('qr/orders/<int:order_id>/approve/', views.api_qr_order_approve, name='qr_order_approve'),
    path('qr/orders/<int:order_id>/reject/', views.api_qr_order_reject, name='qr_order_reject'),
]

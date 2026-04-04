from django.urls import path

from App_Quanly import views

app_name = 'App_Quanly'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('orders/', views.order_history, name='orders'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('categories/', views.category_list_create, name='categories'),
    path('catalog-import/template/', views.catalog_import_template_download, name='catalog_import_template'),
    path('catalog-import/upload/', views.catalog_import_upload, name='catalog_import_upload'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('products/', views.product_list_create, name='products'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:product_pk>/units/add/', views.unit_add, name='unit_add'),
    path('units/<int:pk>/edit/', views.unit_edit, name='unit_edit'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
    path('toppings/', views.topping_list_create, name='toppings'),
    path('toppings/<int:pk>/edit/', views.topping_edit, name='topping_edit'),
    path('toppings/<int:pk>/delete/', views.topping_delete, name='topping_delete'),
    path('product-toppings/', views.product_topping_list_create, name='product_toppings'),
    path('product-toppings/<int:pk>/edit/', views.product_topping_edit, name='product_topping_edit'),
    path('product-toppings/<int:pk>/delete/', views.product_topping_delete, name='product_topping_delete'),
    path('qr-tables/', views.qr_table_list_create, name='qr_tables'),
    path('qr-tables/<int:pk>/edit/', views.qr_table_edit, name='qr_table_edit'),
    path('qr-tables/<int:pk>/delete/', views.qr_table_delete, name='qr_table_delete'),
    path('qr-tables/<int:pk>/reset-token/', views.qr_table_reset_token, name='qr_table_reset_token'),
    path('qr-tables/<int:pk>/png/', views.qr_table_png, name='qr_table_png'),
    path('qr-tables/print-pdf/', views.qr_tables_store_pdf, name='qr_tables_print_pdf'),
    path('payment-qr/', views.payment_qr_settings, name='payment_qr_settings'),
    path('staffs/', views.staff_list_create, name='staffs'),
    path('staffs/<int:pk>/password/', views.staff_password_reset, name='staff_password_reset'),
]

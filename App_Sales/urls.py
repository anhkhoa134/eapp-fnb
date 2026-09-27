from django.urls import path

from App_Sales import views

app_name = 'App_Sales'

urlpatterns = [
    path('', views.pos_page, name='pos'),
    path('orders/today/', views.orders_today_page, name='orders_today'),
    path('kitchen/', views.kitchen_page, name='kitchen'),
    path('kitchen/tickets/<int:ticket_id>/print/', views.kitchen_ticket_print, name='kitchen_ticket_print'),
    path('orders/<int:order_id>/receipt/', views.order_receipt_print, name='order_receipt'),
    path('tables/<int:table_id>/bill/', views.table_bill_print, name='table_bill'),
    path('shifts/', views.shifts_page, name='shifts'),
    path('shifts/<int:shift_id>/print/', views.shift_report_print, name='shift_print'),
]

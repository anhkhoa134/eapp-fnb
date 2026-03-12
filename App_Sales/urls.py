from django.urls import path

from App_Sales import views

app_name = 'App_Sales'

urlpatterns = [
    path('', views.pos_page, name='pos'),
]

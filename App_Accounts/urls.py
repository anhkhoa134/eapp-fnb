from django.urls import path

from App_Accounts import views

app_name = 'App_Accounts'

urlpatterns = [
    path('login/', views.POSLoginView.as_view(), name='login'),
    path('logout/', views.pos_logout, name='logout'),
    path('password/change/', views.password_change, name='password_change'),
]

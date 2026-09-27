from django.urls import path

from App_Accounts import views

app_name = 'App_Accounts'

urlpatterns = [
    path('login/', views.POSLoginView.as_view(), name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.pos_logout, name='logout'),
    path('password/change/', views.password_change, name='password_change'),
    path('password/reset/', views.POSPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.POSPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'password/reset/<uidb64>/<token>/',
        views.POSPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path('password/reset/complete/', views.POSPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]

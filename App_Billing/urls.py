from django.urls import path
from . import views

app_name = 'billing'
urlpatterns = [
    path('requests/', views.requests_view, name='requests'),
    path('requests/<uuid:pk>/cancel/', views.cancel_view, name='cancel'),
]

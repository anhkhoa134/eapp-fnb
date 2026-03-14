from django.urls import path

from App_Public import views

app_name = 'App_Public'

urlpatterns = [
    path('<slug:public_slug>/qr/', views.tenant_qr_ordering, name='tenant_qr_ordering'),
    path('<slug:public_slug>/', views.tenant_catalog, name='tenant_catalog'),
]

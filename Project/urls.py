from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from App_Core.admin_views import demo_seed_reset_confirm

urlpatterns = [
    path(
        f'{settings.REAL_ADMIN_PATH}demo-seed-reset/',
        admin.site.admin_view(demo_seed_reset_confirm),
        name='admin_demo_seed_reset',
    ),
    path(settings.REAL_ADMIN_PATH, admin.site.urls),
    path('accounts/', include(('App_Accounts.urls', 'App_Accounts'), namespace='App_Accounts')),
    path('api/pos/', include(('App_Sales.api_urls', 'App_Sales_API'), namespace='App_Sales_API')),
    path('api/public/', include(('App_Public.api_urls', 'App_Public_API'), namespace='App_Public_API')),
    path('quanly/', include(('App_Quanly.urls', 'App_Quanly'), namespace='App_Quanly')),
    path('', include(('App_Sales.urls', 'App_Sales'), namespace='App_Sales')),
    path('', include(('App_Public.urls', 'App_Public'), namespace='App_Public')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'App_Core.views.redirect_not_found'

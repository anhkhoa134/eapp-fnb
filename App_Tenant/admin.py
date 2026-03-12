from django.contrib import admin

from App_Tenant.models import Store, Tenant, UserStoreAccess


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'public_slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'public_slug')


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'is_active', 'is_default')
    list_filter = ('tenant', 'is_active', 'is_default')
    search_fields = ('name', 'tenant__name')


@admin.register(UserStoreAccess)
class UserStoreAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'store', 'is_default')
    list_filter = ('store__tenant', 'is_default')
    search_fields = ('user__username', 'store__name')

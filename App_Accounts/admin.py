from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from App_Accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'tenant', 'is_active')
    list_filter = ('role', 'tenant', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Tenant POS',
            {
                'fields': ('role', 'tenant'),
            },
        ),
    )

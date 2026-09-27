from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from App_Accounts.forms import ThrottledAdminAuthenticationForm
from App_Accounts.models import LoginAttempt, User

admin.site.login_form = ThrottledAdminAuthenticationForm


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'tenant', 'is_active')
    list_filter = ('role', 'tenant', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Doanh nghiệp',
            {
                'fields': ('role', 'tenant'),
            },
        ),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'failure_count', 'last_failure_at', 'locked_until')
    search_fields = ('username', 'ip_address')
    readonly_fields = ('username', 'ip_address', 'failure_count', 'last_failure_at', 'locked_until')
    actions = ['unlock']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Mở khoá (xoá bộ đếm đăng nhập sai)')
    def unlock(self, request, queryset):
        count, _ = queryset.delete()
        self.message_user(request, f'Đã mở khoá {count} bản ghi.')

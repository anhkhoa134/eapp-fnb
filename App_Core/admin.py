from django.contrib import admin

from App_Core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tenant', 'username', 'action', 'object_type', 'message')
    list_filter = ('action', 'tenant')
    search_fields = ('username', 'message', 'object_repr')
    date_hierarchy = 'created_at'
    list_select_related = ('tenant',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

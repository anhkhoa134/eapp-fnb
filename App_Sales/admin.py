from django.contrib import admin

from App_Sales.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('snapshot_product_name', 'snapshot_unit_name', 'unit_price', 'quantity', 'line_total')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_code', 'tenant', 'store', 'cashier', 'total_amount', 'payment_method', 'created_at')
    list_filter = ('tenant', 'store', 'payment_method', 'status')
    search_fields = ('order_code', 'cashier__username')
    inlines = [OrderItemInline]

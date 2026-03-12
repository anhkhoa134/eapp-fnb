from django.contrib import admin

from App_Sales.models import DiningTable, Order, OrderItem, QROrder, QROrderItem, TableCartItem


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


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'store', 'tenant', 'is_active', 'display_order')
    list_filter = ('tenant', 'store', 'is_active')
    search_fields = ('name', 'code', 'store__name')
    readonly_fields = ('qr_token',)


class QROrderItemInline(admin.TabularInline):
    model = QROrderItem
    extra = 0
    readonly_fields = ('snapshot_product_name', 'snapshot_unit_name', 'unit_price_snapshot', 'quantity', 'line_total')


@admin.register(QROrder)
class QROrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'tenant', 'store', 'table', 'status', 'created_at')
    list_filter = ('tenant', 'store', 'status')
    search_fields = ('table__name', 'table__code')
    inlines = [QROrderItemInline]


@admin.register(TableCartItem)
class TableCartItemAdmin(admin.ModelAdmin):
    list_display = ('table', 'snapshot_product_name', 'snapshot_unit_name', 'quantity', 'source', 'created_at')
    list_filter = ('tenant', 'store', 'source')
    search_fields = ('table__name', 'snapshot_product_name')

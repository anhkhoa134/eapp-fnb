from django import forms
from django.contrib import admin

from App_Accounts.models import User
from App_Catalog.models import Product, ProductUnit, Topping
from App_Sales.models import (
    DiningTable,
    Order,
    OrderItem,
    OrderItemTopping,
    QROrder,
    QROrderItem,
    QROrderItemTopping,
    TableCartItem,
    TableCartItemTopping,
)
from App_Tenant.models import Store


class DiningTableAdminForm(forms.ModelForm):
    class Meta:
        model = DiningTable
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk and self.instance.tenant_id:
            tenant_id = self.instance.tenant_id
        elif self.data is not None:
            t = self.data.get('tenant')
            if t not in (None, ''):
                tenant_id = t
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        tenant = cleaned_data.get('tenant')
        store = cleaned_data.get('store')
        if tenant and store and store.tenant_id != tenant.id:
            self.add_error('store', 'Cửa hàng phải thuộc tenant đã chọn.')
        return cleaned_data


class QROrderAdminForm(forms.ModelForm):
    class Meta:
        model = QROrder
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        store_id = None
        if self.instance.pk:
            tenant_id = self.instance.tenant_id
            store_id = self.instance.store_id
        elif self.data is not None:
            t = self.data.get('tenant')
            if t not in (None, ''):
                tenant_id = t
            s = self.data.get('store')
            if s not in (None, ''):
                store_id = s
                if tenant_id is None:
                    tenant_id = Store.objects.filter(pk=store_id).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
        if store_id:
            self.fields['table'].queryset = DiningTable.objects.filter(store_id=store_id, is_active=True).order_by(
                'display_order', 'name'
            )
        elif tenant_id is not None:
            self.fields['table'].queryset = DiningTable.objects.filter(tenant_id=tenant_id, is_active=True).order_by(
                'store__name', 'display_order', 'name'
            )


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk and self.instance.tenant_id:
            tenant_id = self.instance.tenant_id
        elif self.data is not None:
            t = self.data.get('tenant')
            if t not in (None, ''):
                tenant_id = t
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['cashier'].queryset = User.objects.filter(tenant_id=tenant_id).order_by('username')


class TableCartItemAdminForm(forms.ModelForm):
    class Meta:
        model = TableCartItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        store_id = None
        product_id = None
        if self.instance.pk:
            tenant_id = self.instance.tenant_id
            store_id = self.instance.store_id
            product_id = self.instance.product_id
        elif self.data is not None:
            t = self.data.get('tenant')
            if t not in (None, ''):
                tenant_id = t
            s = self.data.get('store')
            if s not in (None, ''):
                store_id = s
            p = self.data.get('product')
            if p not in (None, ''):
                product_id = p
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['product'].queryset = Product.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['qr_order'].queryset = QROrder.objects.filter(tenant_id=tenant_id).order_by('-created_at')
        if store_id:
            self.fields['table'].queryset = DiningTable.objects.filter(store_id=store_id, is_active=True).order_by(
                'display_order', 'name'
            )
        elif tenant_id is not None:
            self.fields['table'].queryset = DiningTable.objects.filter(tenant_id=tenant_id, is_active=True).order_by(
                'store__name', 'display_order', 'name'
            )
        if product_id:
            self.fields['unit'].queryset = ProductUnit.objects.filter(product_id=product_id, is_active=True).order_by(
                'display_order', 'name'
            )


class TableCartItemToppingAdminForm(forms.ModelForm):
    class Meta:
        model = TableCartItemTopping
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk and self.instance.table_cart_item_id:
            tenant_id = self.instance.table_cart_item.tenant_id
        elif self.data is not None:
            tcid = self.data.get('table_cart_item')
            if tcid not in (None, ''):
                tenant_id = TableCartItem.objects.filter(pk=tcid).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['topping'].queryset = Topping.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')


class QROrderItemToppingAdminForm(forms.ModelForm):
    class Meta:
        model = QROrderItemTopping
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk and self.instance.qr_order_item_id:
            tenant_id = self.instance.qr_order_item.qr_order.tenant_id
        elif self.data is not None:
            oi = self.data.get('qr_order_item')
            if oi not in (None, ''):
                tenant_id = (
                    QROrderItem.objects.filter(pk=oi).values_list('qr_order__tenant_id', flat=True).first()
                )
        if tenant_id is not None:
            self.fields['topping'].queryset = Topping.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')


class OrderItemToppingAdminForm(forms.ModelForm):
    class Meta:
        model = OrderItemTopping
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk and self.instance.order_item_id:
            tenant_id = self.instance.order_item.order.tenant_id
        elif self.data is not None:
            oi = self.data.get('order_item')
            if oi not in (None, ''):
                tenant_id = OrderItem.objects.filter(pk=oi).values_list('order__tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['topping'].queryset = Topping.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('snapshot_product_name', 'snapshot_unit_name', 'unit_price', 'quantity', 'line_total')


class OrderItemToppingInline(admin.TabularInline):
    model = OrderItemTopping
    extra = 0
    readonly_fields = ('snapshot_topping_name', 'snapshot_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ('order_code', 'tenant', 'store', 'cashier', 'total_amount', 'payment_method', 'created_at')
    list_filter = ('tenant', 'store', 'payment_method', 'status')
    search_fields = ('order_code', 'cashier__username')
    inlines = [OrderItemInline]


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    form = DiningTableAdminForm
    list_display = ('name', 'code', 'store', 'tenant', 'is_active', 'display_order')
    list_filter = ('tenant', 'store', 'is_active')
    search_fields = ('name', 'code', 'store__name')
    readonly_fields = ('qr_token',)


class QROrderItemInline(admin.TabularInline):
    model = QROrderItem
    extra = 0
    readonly_fields = ('snapshot_product_name', 'snapshot_unit_name', 'unit_price_snapshot', 'quantity', 'line_total')


class QROrderItemToppingInline(admin.TabularInline):
    model = QROrderItemTopping
    extra = 0
    readonly_fields = ('snapshot_topping_name', 'snapshot_price')


@admin.register(QROrder)
class QROrderAdmin(admin.ModelAdmin):
    form = QROrderAdminForm
    list_display = ('id', 'tenant', 'store', 'table', 'status', 'created_at')
    list_filter = ('tenant', 'store', 'status')
    search_fields = ('table__name', 'table__code')
    inlines = [QROrderItemInline]


@admin.register(TableCartItem)
class TableCartItemAdmin(admin.ModelAdmin):
    form = TableCartItemAdminForm
    list_display = ('table', 'snapshot_product_name', 'snapshot_unit_name', 'quantity', 'source', 'created_at')
    list_filter = ('tenant', 'store', 'source')
    search_fields = ('table__name', 'snapshot_product_name')


@admin.register(TableCartItemTopping)
class TableCartItemToppingAdmin(admin.ModelAdmin):
    form = TableCartItemToppingAdminForm
    list_display = ('table_cart_item', 'snapshot_topping_name', 'snapshot_price')
    list_filter = ('table_cart_item__tenant',)


@admin.register(QROrderItemTopping)
class QROrderItemToppingAdmin(admin.ModelAdmin):
    form = QROrderItemToppingAdminForm
    list_display = ('qr_order_item', 'snapshot_topping_name', 'snapshot_price')
    list_filter = ('qr_order_item__qr_order__tenant',)


@admin.register(OrderItemTopping)
class OrderItemToppingAdmin(admin.ModelAdmin):
    form = OrderItemToppingAdminForm
    list_display = ('order_item', 'snapshot_topping_name', 'snapshot_price')
    list_filter = ('order_item__order__tenant',)

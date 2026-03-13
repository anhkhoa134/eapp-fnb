import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from App_Core.models import TimeStampedModel


def generate_qr_token():
    return secrets.token_urlsafe(24)


class Order(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card/QR'

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.PROTECT, related_name='orders')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.PROTECT, related_name='orders')
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    order_code = models.CharField(max_length=30, unique=True, editable=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    customer_paid = models.DecimalField(max_digits=14, decimal_places=2)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'created_at']),
            models.Index(fields=['tenant', 'status', 'created_at']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = f'ORD-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_code


class DiningTable(TimeStampedModel):
    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='dining_tables')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='dining_tables')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    qr_token = models.CharField(max_length=64, unique=True, default=generate_qr_token, editable=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['store', 'code'], name='uq_dining_table_store_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'store', 'is_active']),
            models.Index(fields=['store', 'display_order']),
        ]
        ordering = ['display_order', 'id']

    def clean(self):
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Store và tenant của bàn phải khớp nhau.')

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        if not self.qr_token:
            self.qr_token = generate_qr_token()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class QROrder(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='qr_orders')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='qr_orders')
    table = models.ForeignKey(DiningTable, on_delete=models.CASCADE, related_name='qr_orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    customer_note = models.CharField(max_length=255, blank=True)
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_qr_orders',
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_qr_orders',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'status', 'created_at']),
            models.Index(fields=['table', 'status', 'created_at']),
        ]
        ordering = ['-created_at']

    def clean(self):
        if self.table_id and self.store_id and self.table.store_id != self.store_id:
            raise ValidationError('Table phải thuộc store của đơn QR.')
        if self.table_id and self.tenant_id and self.table.tenant_id != self.tenant_id:
            raise ValidationError('Table phải cùng tenant với đơn QR.')
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Store phải cùng tenant với đơn QR.')

    def __str__(self):
        return f'QR-{self.id or "new"}-{self.status}'


class QROrderItem(TimeStampedModel):
    qr_order = models.ForeignKey(QROrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('App_Catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('App_Catalog.ProductUnit', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_product_name = models.CharField(max_length=180)
    snapshot_unit_name = models.CharField(max_length=120)
    unit_price_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=['qr_order', 'snapshot_product_name']),
        ]

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError('Số lượng phải lớn hơn 0.')

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price_snapshot * self.quantity
        self.full_clean()
        super().save(*args, **kwargs)


class QROrderItemTopping(TimeStampedModel):
    qr_order_item = models.ForeignKey(QROrderItem, on_delete=models.CASCADE, related_name='toppings')
    topping = models.ForeignKey('App_Catalog.Topping', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_topping_name = models.CharField(max_length=120)
    snapshot_price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['qr_order_item', 'topping'], name='uq_qr_order_item_topping'),
        ]
        indexes = [
            models.Index(fields=['qr_order_item', 'snapshot_topping_name']),
        ]
        ordering = ['id']

    def clean(self):
        if self.snapshot_price < 0:
            raise ValidationError('Giá topping snapshot phải >= 0.')
        if self.topping_id and self.qr_order_item_id:
            if self.topping.tenant_id != self.qr_order_item.qr_order.tenant_id:
                raise ValidationError('Topping phải cùng tenant với đơn QR item.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TableCartItem(TimeStampedModel):
    class Source(models.TextChoices):
        STAFF = 'STAFF', 'Staff'
        QR = 'QR', 'QR'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='table_cart_items')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='table_cart_items')
    table = models.ForeignKey(DiningTable, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey('App_Catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('App_Catalog.ProductUnit', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_product_name = models.CharField(max_length=180)
    snapshot_unit_name = models.CharField(max_length=120)
    unit_price_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.STAFF)
    qr_order = models.ForeignKey(QROrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'table', 'created_at']),
            models.Index(fields=['table', 'source', 'created_at']),
        ]

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError('Số lượng phải lớn hơn 0.')
        if self.table_id and self.store_id and self.table.store_id != self.store_id:
            raise ValidationError('Table phải thuộc store của cart item.')
        if self.table_id and self.tenant_id and self.table.tenant_id != self.tenant_id:
            raise ValidationError('Table phải cùng tenant với cart item.')
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Store phải cùng tenant với cart item.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TableCartItemTopping(TimeStampedModel):
    table_cart_item = models.ForeignKey(TableCartItem, on_delete=models.CASCADE, related_name='toppings')
    topping = models.ForeignKey('App_Catalog.Topping', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_topping_name = models.CharField(max_length=120)
    snapshot_price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['table_cart_item', 'topping'], name='uq_table_cart_item_topping'),
        ]
        indexes = [
            models.Index(fields=['table_cart_item', 'snapshot_topping_name']),
        ]
        ordering = ['id']

    def clean(self):
        if self.snapshot_price < 0:
            raise ValidationError('Giá topping snapshot phải >= 0.')
        if self.topping_id and self.table_cart_item_id:
            if self.topping.tenant_id != self.table_cart_item.tenant_id:
                raise ValidationError('Topping phải cùng tenant với cart item.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('App_Catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('App_Catalog.ProductUnit', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_product_name = models.CharField(max_length=180)
    snapshot_unit_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=['order', 'snapshot_product_name']),
        ]

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.snapshot_product_name} x{self.quantity}'


class OrderItemTopping(TimeStampedModel):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='toppings')
    topping = models.ForeignKey('App_Catalog.Topping', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_topping_name = models.CharField(max_length=120)
    snapshot_price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order_item', 'topping'], name='uq_order_item_topping'),
        ]
        indexes = [
            models.Index(fields=['order_item', 'snapshot_topping_name']),
        ]
        ordering = ['id']

    def clean(self):
        if self.snapshot_price < 0:
            raise ValidationError('Giá topping snapshot phải >= 0.')
        if self.topping_id and self.order_item_id:
            if self.topping.tenant_id != self.order_item.order.tenant_id:
                raise ValidationError('Topping phải cùng tenant với order item.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

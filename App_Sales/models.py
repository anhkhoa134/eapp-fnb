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

    class SaleChannel(models.TextChoices):
        DINE_IN = 'dine_in', 'Tại quán'
        TAKEAWAY = 'takeaway', 'Mang về'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.PROTECT, related_name='orders')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.PROTECT, related_name='orders')
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    customer = models.ForeignKey(
        'App_Sales.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    promotion = models.ForeignKey(
        'App_Sales.Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    order_code = models.CharField(max_length=30, unique=True, editable=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    sale_channel = models.CharField(
        'Kênh bán',
        max_length=20,
        choices=SaleChannel.choices,
        null=True,
        blank=True,
        help_text='Thanh toán tại bàn (POS) hay mang về (checkout giỏ). Đơn cũ có thể để trống.',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_snapshot_name = models.CharField(max_length=150, blank=True)
    promotion_snapshot_type = models.CharField(max_length=20, blank=True)
    promotion_snapshot_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    customer_paid = models.DecimalField(max_digits=14, decimal_places=2)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'created_at']),
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['tenant', 'customer', 'created_at']),
            models.Index(fields=['tenant', 'promotion', 'created_at']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = f'ORD-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_code


class Customer(TimeStampedModel):
    class Tier(models.TextChoices):
        MEMBER = 'member', 'Member'
        SILVER = 'silver', 'Silver'
        GOLD = 'gold', 'Gold'
        VIP = 'vip', 'VIP'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=24)
    email = models.EmailField(blank=True)
    note = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    points_balance = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.MEMBER)
    last_order_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'phone'], name='uq_customer_tenant_phone'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'name']),
            models.Index(fields=['tenant', 'phone']),
            models.Index(fields=['tenant', 'tier']),
        ]
        ordering = ['name', 'id']
        verbose_name = 'Khách hàng'
        verbose_name_plural = 'Khách hàng'

    def clean(self):
        self.name = (self.name or '').strip()
        self.phone = (self.phone or '').strip()
        self.email = (self.email or '').strip()
        if not self.name:
            raise ValidationError({'name': 'Vui lòng nhập tên khách hàng.'})
        if not self.phone:
            raise ValidationError({'phone': 'Vui lòng nhập số điện thoại.'})
        digits = ''.join(ch for ch in self.phone if ch.isdigit())
        if len(digits) < 8:
            raise ValidationError({'phone': 'Số điện thoại quá ngắn hoặc không hợp lệ.'})
        if self.total_spent < 0:
            raise ValidationError({'total_spent': 'Tổng chi tiêu không được âm.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} - {self.phone}'


class Promotion(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Giảm %'
        FIXED = 'fixed', 'Giảm tiền'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='promotions')
    stores = models.ManyToManyField('App_Tenant.Store', related_name='promotions', blank=True)
    name = models.CharField(max_length=150)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=14, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField('Đang hoạt động', default=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'valid_from', 'valid_to']),
        ]
        ordering = ['-is_active', '-created_at']
        verbose_name = 'Khuyến mãi'
        verbose_name_plural = 'Khuyến mãi'

    def clean(self):
        self.name = (self.name or '').strip()
        if not self.name:
            raise ValidationError({'name': 'Vui lòng nhập tên khuyến mãi.'})
        if self.discount_value <= 0:
            raise ValidationError({'discount_value': 'Giá trị giảm phải lớn hơn 0.'})
        if self.discount_type == self.DiscountType.PERCENT and self.discount_value > 100:
            raise ValidationError({'discount_value': 'Giảm theo phần trăm không được vượt quá 100%.'})
        if self.min_order_amount < 0:
            raise ValidationError({'min_order_amount': 'Điều kiện đơn tối thiểu không được âm.'})
        if self.max_discount_amount is not None and self.max_discount_amount < 0:
            raise ValidationError({'max_discount_amount': 'Giới hạn giảm tối đa không được âm.'})
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError({'valid_to': 'Thời gian kết thúc phải sau thời gian bắt đầu.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DiningTable(TimeStampedModel):
    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='dining_tables')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='dining_tables')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    qr_token = models.CharField(max_length=64, unique=True, default=generate_qr_token, editable=False)
    is_active = models.BooleanField('Đang hoạt động', default=True)
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
            raise ValidationError('Cửa hàng và doanh nghiệp của bàn phải khớp nhau.')

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
        CANCELLED = 'CANCELLED', 'Cancelled'

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
    rejection_reason = models.CharField('Lý do từ chối', max_length=500, blank=True)
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
            raise ValidationError('Bàn phải cùng doanh nghiệp với đơn QR.')
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Cửa hàng phải cùng doanh nghiệp với đơn QR.')

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
                raise ValidationError('Topping phải cùng doanh nghiệp với món trong đơn QR.')

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
            raise ValidationError('Bàn phải cùng doanh nghiệp với mục giỏ hàng.')
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Cửa hàng phải cùng doanh nghiệp với mục giỏ hàng.')

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
                raise ValidationError('Topping phải cùng doanh nghiệp với mục giỏ hàng.')

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
                raise ValidationError('Topping phải cùng doanh nghiệp với món trong đơn bán.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

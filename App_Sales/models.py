import secrets
import uuid
from decimal import Decimal

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
        REFUNDED = 'refunded', 'Đã hoàn tiền'

    class SaleChannel(models.TextChoices):
        DINE_IN = 'dine_in', 'Tại quán'
        TAKEAWAY = 'takeaway', 'Mang về'

    class DiscountSource(models.TextChoices):
        NONE = 'none', 'Không giảm'
        PROMOTION = 'promotion', 'Khuyến mãi'
        TIER = 'tier', 'Ưu đãi hạng'

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
    discount_source = models.CharField(max_length=20, choices=DiscountSource.choices, default=DiscountSource.NONE)
    promotion_snapshot_name = models.CharField(max_length=150, blank=True)
    promotion_snapshot_type = models.CharField(max_length=20, blank=True)
    promotion_snapshot_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tier_snapshot = models.CharField(max_length=20, blank=True)
    tier_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tier_discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    customer_paid = models.DecimalField(max_digits=14, decimal_places=2)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    table_name = models.CharField('Bàn', max_length=120, blank=True)
    refunded_amount = models.DecimalField('Đã hoàn tiền', max_digits=14, decimal_places=2, default=0)
    print_count = models.PositiveIntegerField('Số lần in hoá đơn', default=0)

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

    @property
    def refundable_amount(self) -> Decimal:
        if self.status == self.Status.CANCELLED:
            return Decimal('0')
        return max(Decimal('0'), self.total_amount - self.refunded_amount)

    @property
    def net_amount(self) -> Decimal:
        return self.total_amount - self.refunded_amount

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


class CustomerTierSetting(TimeStampedModel):
    DEFAULTS = {
        Customer.Tier.MEMBER: (Decimal('0'), Decimal('0')),
        Customer.Tier.SILVER: (Decimal('5000000'), Decimal('3')),
        Customer.Tier.GOLD: (Decimal('20000000'), Decimal('5')),
        Customer.Tier.VIP: (Decimal('50000000'), Decimal('10')),
    }
    TIER_ORDER = [
        Customer.Tier.MEMBER,
        Customer.Tier.SILVER,
        Customer.Tier.GOLD,
        Customer.Tier.VIP,
    ]

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='customer_tier_settings')
    tier = models.CharField(max_length=20, choices=Customer.Tier.choices)
    min_total_spent = models.DecimalField(max_digits=14, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'tier'], name='uq_customer_tier_setting_tenant_tier'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'tier'], name='App_Sales_c_tenant__8af4bc_idx'),
        ]
        ordering = ['min_total_spent', 'id']
        verbose_name = 'Cấu hình hạng khách hàng'
        verbose_name_plural = 'Cấu hình hạng khách hàng'

    @classmethod
    def default_rows(cls):
        return [
            {
                'tier': tier,
                'min_total_spent': cls.DEFAULTS[tier][0],
                'discount_percent': cls.DEFAULTS[tier][1],
            }
            for tier in cls.TIER_ORDER
        ]

    @classmethod
    def ensure_defaults_for_tenant(cls, tenant):
        if not tenant:
            return []
        existing = {row.tier: row for row in cls.objects.filter(tenant=tenant)}
        created = []
        for row in cls.default_rows():
            if row['tier'] in existing:
                continue
            created.append(
                cls(
                    tenant=tenant,
                    tier=row['tier'],
                    min_total_spent=row['min_total_spent'],
                    discount_percent=row['discount_percent'],
                )
            )
        if created:
            cls.objects.bulk_create(created)
        return list(cls.objects.filter(tenant=tenant).order_by('min_total_spent', 'id'))

    @classmethod
    def validate_tier_rows(cls, rows):
        by_tier = {row['tier']: row for row in rows}
        missing = [tier for tier in cls.TIER_ORDER if tier not in by_tier]
        if missing:
            raise ValidationError('Thiếu cấu hình hạng khách hàng.')
        if by_tier[Customer.Tier.MEMBER]['min_total_spent'] != Decimal('0'):
            raise ValidationError('Ngưỡng Member phải bằng 0.')
        previous = None
        for tier in cls.TIER_ORDER:
            min_total_spent = by_tier[tier]['min_total_spent']
            discount_percent = by_tier[tier]['discount_percent']
            if min_total_spent < 0:
                raise ValidationError('Ngưỡng tổng chi tiêu không được âm.')
            if discount_percent < 0 or discount_percent > 100:
                raise ValidationError('Phần trăm ưu đãi phải từ 0 đến 100.')
            if previous is not None and min_total_spent <= previous:
                raise ValidationError('Ngưỡng hạng phải tăng dần từ Member đến VIP.')
            previous = min_total_spent

    def clean(self):
        if self.min_total_spent is None or self.discount_percent is None:
            return
        if self.tier == Customer.Tier.MEMBER and self.min_total_spent != Decimal('0'):
            raise ValidationError({'min_total_spent': 'Ngưỡng Member phải bằng 0.'})
        if self.min_total_spent < 0:
            raise ValidationError({'min_total_spent': 'Ngưỡng tổng chi tiêu không được âm.'})
        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({'discount_percent': 'Phần trăm ưu đãi phải từ 0 đến 100.'})
        rows = []
        if self.tenant_id:
            settings = CustomerTierSetting.objects.filter(tenant=self.tenant)
            if self.pk:
                settings = settings.exclude(pk=self.pk)
            for row in settings:
                rows.append(
                    {
                        'tier': row.tier,
                        'min_total_spent': row.min_total_spent,
                        'discount_percent': row.discount_percent,
                    }
                )
        rows.append(
            {
                'tier': self.tier,
                'min_total_spent': self.min_total_spent,
                'discount_percent': self.discount_percent,
            }
        )
        if len({row['tier'] for row in rows}) == len(CustomerTierSetting.TIER_ORDER):
            CustomerTierSetting.validate_tier_rows(rows)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tenant} - {self.get_tier_display()}'


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

    class OrderType(models.TextChoices):
        DINE_IN = 'DINE_IN', 'Tại bàn'
        TAKEAWAY = 'TAKEAWAY', 'Mang đi'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='qr_orders')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='qr_orders')
    table = models.ForeignKey(
        DiningTable,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qr_orders',
        help_text='Để trống với đơn mang đi đặt từ trang menu.',
    )
    order_type = models.CharField('Loại đơn', max_length=12, choices=OrderType.choices, default=OrderType.DINE_IN)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    customer_name = models.CharField('Tên khách', max_length=120, blank=True)
    customer_phone = models.CharField('SĐT khách', max_length=20, blank=True)
    access_key = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        editable=False,
        help_text='Khoá để khách mang đi xem / sửa / huỷ đơn của mình.',
    )
    sale_order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_order',
        help_text='Hoá đơn POS đã thu tiền cho đơn mang đi.',
    )
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
        if self.order_type == self.OrderType.DINE_IN and not self.table_id:
            raise ValidationError('Đơn tại bàn phải có bàn.')
        if self.table_id and self.store_id and self.table.store_id != self.store_id:
            raise ValidationError('Table phải thuộc store của đơn QR.')
        if self.table_id and self.tenant_id and self.table.tenant_id != self.tenant_id:
            raise ValidationError('Bàn phải cùng doanh nghiệp với đơn QR.')
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError('Cửa hàng phải cùng doanh nghiệp với đơn QR.')

    @property
    def is_takeaway(self) -> bool:
        return self.order_type == self.OrderType.TAKEAWAY

    @property
    def display_label(self) -> str:
        if self.is_takeaway:
            return f'Mang đi · {self.customer_name}' if self.customer_name else 'Mang đi'
        return self.table.name if self.table_id else ''

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
    kitchen_sent_quantity = models.PositiveIntegerField('Số lượng đã báo bếp', default=0)

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


class KitchenTicket(TimeStampedModel):
    class Source(models.TextChoices):
        TABLE = 'TABLE', 'Tại bàn'
        QR = 'QR', 'Gọi món QR'
        TAKEAWAY = 'TAKEAWAY', 'Mang về'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='kitchen_tickets')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='kitchen_tickets')
    table = models.ForeignKey(
        DiningTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kitchen_tickets',
    )
    table_name = models.CharField('Tên bàn / nhãn phiếu', max_length=120, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.TABLE)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='kitchen_tickets')
    qr_order = models.ForeignKey(
        QROrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kitchen_tickets',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kitchen_tickets',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    print_count = models.PositiveIntegerField('Số lần in phiếu', default=0)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'completed_at', 'created_at']),
            models.Index(fields=['table', 'completed_at']),
        ]
        ordering = ['created_at', 'id']
        verbose_name = 'Phiếu bếp'
        verbose_name_plural = 'Phiếu bếp'

    def __str__(self):
        return f'KT-{self.id or "new"} {self.table_name}'


class KitchenTicketItem(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Chờ làm'
        PREPARING = 'PREPARING', 'Đang làm'
        DONE = 'DONE', 'Đã xong'
        CANCELLED = 'CANCELLED', 'Đã huỷ'

    OPEN_STATUSES = (Status.PENDING, Status.PREPARING)

    ticket = models.ForeignKey(KitchenTicket, on_delete=models.CASCADE, related_name='items')
    table_cart_item = models.ForeignKey(
        TableCartItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kitchen_items',
    )
    product = models.ForeignKey('App_Catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_product_name = models.CharField(max_length=180)
    snapshot_unit_name = models.CharField(max_length=120, blank=True)
    toppings_text = models.CharField(max_length=500, blank=True)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['ticket', 'status']),
            models.Index(fields=['table_cart_item', 'status']),
        ]
        ordering = ['id']
        verbose_name = 'Món trong phiếu bếp'
        verbose_name_plural = 'Món trong phiếu bếp'

    def __str__(self):
        return f'{self.snapshot_product_name} x{self.quantity} ({self.status})'


class Refund(TimeStampedModel):
    """Một lần hoàn tiền cho đơn bán (toàn bộ hoặc một phần)."""

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='refunds')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='refunds')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField('Số tiền hoàn', max_digits=14, decimal_places=2)
    method = models.CharField('Hình thức hoàn', max_length=20, choices=Order.PaymentMethod.choices)
    reason = models.CharField('Lý do', max_length=255)
    is_full = models.BooleanField('Hoàn toàn bộ', default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
    )

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'store', 'created_at']),
        ]
        ordering = ['-created_at', '-id']
        verbose_name = 'Hoàn tiền'
        verbose_name_plural = 'Hoàn tiền'

    def __str__(self):
        return f'{self.order.order_code} -{self.amount}'


class Shift(TimeStampedModel):
    """Ca làm việc theo cửa hàng: mở ca với tiền đầu ca, chốt ca đối soát tiền mặt."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Đang mở'
        CLOSED = 'CLOSED', 'Đã chốt'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='shifts')
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='shifts')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opened_shifts',
    )
    opened_at = models.DateTimeField('Mở ca lúc')
    opening_cash = models.DecimalField('Tiền đầu ca', max_digits=14, decimal_places=2, default=0)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_shifts',
    )
    closed_at = models.DateTimeField('Chốt ca lúc', null=True, blank=True)
    # Số liệu chốt lại tại thời điểm đóng ca (không đổi dù đơn bị sửa/xoá sau này).
    order_count = models.PositiveIntegerField('Số đơn', default=0)
    gross_sales = models.DecimalField('Doanh thu', max_digits=14, decimal_places=2, default=0)
    cash_sales = models.DecimalField('Thu tiền mặt', max_digits=14, decimal_places=2, default=0)
    card_sales = models.DecimalField('Thu thẻ/QR', max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField('Giảm giá', max_digits=14, decimal_places=2, default=0)
    refund_total = models.DecimalField('Hoàn tiền', max_digits=14, decimal_places=2, default=0)
    cash_refunds = models.DecimalField('Hoàn tiền mặt', max_digits=14, decimal_places=2, default=0)
    expected_cash = models.DecimalField('Tiền mặt dự kiến', max_digits=14, decimal_places=2, null=True, blank=True)
    counted_cash = models.DecimalField('Tiền mặt thực đếm', max_digits=14, decimal_places=2, null=True, blank=True)
    cash_difference = models.DecimalField('Chênh lệch', max_digits=14, decimal_places=2, null=True, blank=True)
    note = models.CharField('Ghi chú', max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['store'],
                condition=models.Q(status='OPEN'),
                name='uq_open_shift_per_store',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'store', 'opened_at']),
            models.Index(fields=['tenant', 'status']),
        ]
        ordering = ['-opened_at', '-id']
        verbose_name = 'Ca làm việc'
        verbose_name_plural = 'Ca làm việc'

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    def __str__(self):
        return f'Ca #{self.id or "new"} - {self.store.name}'

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from App_Core.models import TimeStampedModel
from App_Core.tenant_media_paths import store_payment_qr_upload_to

RESERVED_PUBLIC_SLUGS = {
    'admin',
    'accounts',
    'api',
    'quanly',
    'kitchen',
    'shifts',
    'static',
    'media',
    'offline',
    'favicon.ico',
    'orders',
    'tables',
}

# Mức thuế tối đa cho phép nhập ở Cấu hình tính năng (chặn gõ nhầm, VD 80 thay vì 8).
MAX_TAX_PERCENT = Decimal('30')


def _build_unique_slug(queryset, source_name, fallback='item'):
    base_slug = slugify(source_name) or fallback
    candidate = base_slug
    suffix = 2
    while queryset.filter(slug=candidate).exists():
        candidate = f'{base_slug}-{suffix}'
        suffix += 1
    return candidate


def validate_public_slug(value):
    if (value or '').strip().lower() in RESERVED_PUBLIC_SLUGS:
        raise ValidationError('Public slug trùng với route hệ thống, vui lòng chọn slug khác.')


class SubscriptionPlan(TimeStampedModel):
    """Mẫu gói cước. Gán gói cho doanh nghiệp sẽ chép giới hạn + tắt tính năng không có trong gói."""

    name = models.CharField('Tên gói', max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    price_yearly = models.DecimalField('Giá / năm', max_digits=12, decimal_places=0, default=0)
    is_contact_price = models.BooleanField(
        'Giá liên hệ',
        default=False,
        help_text='Bật để hiển thị "Liên hệ" thay vì giá cụ thể.',
    )
    tagline = models.CharField('Mô tả ngắn', max_length=150, blank=True)
    highlight = models.CharField('Nhãn nổi bật', max_length=60, blank=True, help_text='Ví dụ: "Phổ biến nhất".')
    max_stores = models.PositiveIntegerField('Giới hạn cửa hàng', null=True, blank=True, help_text='Để trống = không giới hạn.')
    max_staff_users = models.PositiveIntegerField(
        'Giới hạn nhân viên',
        null=True,
        blank=True,
        help_text='Để trống = không giới hạn. 0 = không có tài khoản nhân viên (chỉ 1 quản lý).',
    )
    max_dining_tables = models.PositiveIntegerField('Giới hạn bàn', null=True, blank=True, help_text='Để trống = không giới hạn.')
    max_products = models.PositiveIntegerField('Giới hạn món', null=True, blank=True, help_text='Để trống = không giới hạn.')
    feature_customer = models.BooleanField('Khách hàng thân thiết', default=True)
    feature_promotion = models.BooleanField('Khuyến mãi', default=True)
    feature_qr_order = models.BooleanField('QR bàn / gọi món QR', default=True)
    feature_kitchen = models.BooleanField('Màn hình bếp', default=True)
    feature_shift = models.BooleanField('Ca làm việc (chốt ca)', default=True)
    feature_recipe = models.BooleanField('Định mức nguyên liệu', default=True)
    is_default = models.BooleanField(
        'Gói đăng ký mặc định',
        default=False,
        help_text='Gói gán cho doanh nghiệp tự đăng ký tại trang Đăng ký.',
    )
    sort_order = models.PositiveIntegerField('Thứ tự', default=0)

    # Cờ tính năng của gói -> cờ bật/tắt tương ứng trên Tenant.
    TENANT_FEATURE_FIELDS = {
        'feature_customer': 'show_customer_feature',
        'feature_promotion': 'show_promotion_feature',
        'feature_qr_order': 'show_qr_order_feature',
        'feature_kitchen': 'show_kitchen_feature',
        'feature_shift': 'show_shift_feature',
        'feature_recipe': 'show_recipe_feature',
    }
    LIMIT_FIELDS = ('max_stores', 'max_staff_users', 'max_dining_tables', 'max_products')

    class Meta:
        ordering = ['sort_order', 'price_yearly']
        verbose_name = 'Gói cước'
        verbose_name_plural = 'Gói cước'

    def __str__(self):
        return self.name

    @property
    def is_free(self) -> bool:
        return not self.is_contact_price and not self.price_yearly

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(
                SubscriptionPlan.objects.exclude(pk=self.pk),
                source_name=self.name,
                fallback='plan',
            )
        super().save(*args, **kwargs)


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=150)
    public_slug = models.SlugField(max_length=120, unique=True, validators=[validate_public_slug])
    is_active = models.BooleanField('Đang hoạt động', default=True)
    show_store_feature = models.BooleanField(
        'Quản lý nhiều cửa hàng',
        default=False,
        help_text='Tắt: doanh nghiệp chỉ dùng 1 cửa hàng mặc định. Bật để mở rộng nhiều cửa hàng (vẫn theo giới hạn gói).',
    )
    show_customer_feature = models.BooleanField('Hiển thị Khách hàng', default=True)
    show_promotion_feature = models.BooleanField('Hiển thị Khuyến mãi', default=True)
    show_topping_feature = models.BooleanField('Hiển thị Topping / tuỳ chọn món', default=True)
    show_qr_order_feature = models.BooleanField('Hiển thị QR bàn / gọi món QR', default=True)
    show_kitchen_feature = models.BooleanField('Màn hình bếp (báo bếp)', default=False)
    show_shift_feature = models.BooleanField('Ca làm việc (chốt ca)', default=False)
    show_recipe_feature = models.BooleanField('Định mức nguyên liệu', default=False)
    tax_percent = models.DecimalField(
        'Thuế (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(MAX_TAX_PERCENT)],
        help_text='Thuế cộng vào hoá đơn, tính trên số tiền sau giảm giá. 0 = không tính thuế.',
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        related_name='tenants',
        null=True,
        blank=True,
        verbose_name='Gói cước',
    )
    max_stores = models.PositiveIntegerField(
        'Giới hạn cửa hàng',
        default=1,
        null=True,
        blank=True,
        help_text='Số cửa hàng tối đa. Để trống = không giới hạn.',
    )
    max_dining_tables = models.PositiveIntegerField(
        'Giới hạn bàn',
        default=12,
        null=True,
        blank=True,
        help_text='Tổng số bàn (QR/POS) tối đa. Để trống = không giới hạn.',
    )
    max_staff_users = models.PositiveIntegerField(
        'Giới hạn nhân viên',
        default=2,
        null=True,
        blank=True,
        help_text='Số tài khoản nhân viên (không tính quản lý). Để trống = không giới hạn, 0 = không có nhân viên.',
    )
    max_products = models.PositiveIntegerField(
        'Giới hạn món',
        null=True,
        blank=True,
        help_text='Số món (sản phẩm) tối đa. Để trống = không giới hạn.',
    )
    subscription_starts_on = models.DateField(
        'Ngày bắt đầu gói',
        null=True,
        blank=True,
        help_text='Để trống khi tạo mới: hệ thống gán ngày hiện tại.',
    )
    subscription_ends_on = models.DateField(
        'Ngày kết thúc gói',
        null=True,
        blank=True,
        help_text='Để trống khi tạo mới: mặc định 1 năm sau ngày bắt đầu.',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Doanh nghiệp'
        verbose_name_plural = 'Doanh nghiệp'

    def clean(self):
        if self.tax_percent is None:
            self.tax_percent = Decimal('0')
        self.public_slug = (self.public_slug or '').strip().lower()
        validate_public_slug(self.public_slug)
        if self.subscription_starts_on and self.subscription_ends_on:
            if self.subscription_ends_on < self.subscription_starts_on:
                raise ValidationError(
                    {'subscription_ends_on': 'Ngày kết thúc phải sau hoặc cùng ngày bắt đầu gói.'}
                )

    def save(self, *args, **kwargs):
        if self._state.adding:
            today = timezone.now().date()
            if self.subscription_starts_on is None:
                self.subscription_starts_on = today
            # Gói miễn phí không có ngày hết hạn.
            is_free_plan = self.subscription_plan is not None and self.subscription_plan.is_free
            if self.subscription_ends_on is None and not is_free_plan:
                self.subscription_ends_on = self.subscription_starts_on + timedelta(days=365)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def apply_subscription_plan(self, plan):
        """Gán gói: chép giới hạn của gói và tắt các tính năng gói không bao gồm. Không tự lưu."""
        self.subscription_plan = plan
        if plan is None:
            return
        for field in SubscriptionPlan.LIMIT_FIELDS:
            setattr(self, field, getattr(plan, field))
        for plan_field, tenant_field in SubscriptionPlan.TENANT_FEATURE_FIELDS.items():
            if not getattr(plan, plan_field):
                setattr(self, tenant_field, False)
        if plan.is_free:
            self.subscription_ends_on = None
        elif self.subscription_ends_on is None:
            today = timezone.now().date()
            self.subscription_starts_on = today
            self.subscription_ends_on = today + timedelta(days=365)

    def plan_allows_feature(self, tenant_field) -> bool:
        """Tính năng có nằm trong gói hiện tại không (không có gói = không khoá)."""
        plan = self.subscription_plan
        if plan is None:
            return True
        for plan_field, mapped_field in SubscriptionPlan.TENANT_FEATURE_FIELDS.items():
            if mapped_field == tenant_field:
                return bool(getattr(plan, plan_field))
        return True

    def feature_enabled(self, tenant_field) -> bool:
        """Tính năng dùng được: cờ tenant đang bật và gói hiện tại cho phép."""
        return bool(getattr(self, tenant_field)) and self.plan_allows_feature(tenant_field)

    @property
    def customer_feature_enabled(self) -> bool:
        return self.feature_enabled('show_customer_feature')

    @property
    def promotion_feature_enabled(self) -> bool:
        return self.feature_enabled('show_promotion_feature')

    @property
    def recipe_feature_enabled(self) -> bool:
        return self.feature_enabled('show_recipe_feature')

    @property
    def tax_rate(self) -> Decimal:
        """Tỷ lệ thuế dạng thập phân (10% -> 0.1) dùng khi tính hoá đơn."""
        return (self.tax_percent or Decimal('0')) / Decimal('100')

    def is_ordering_open(self) -> bool:
        """Khách được đặt món online / gọi món QR: bật tính năng QR, doanh nghiệp hoạt động và gói còn hạn."""
        return self.is_active and self.show_qr_order_feature and not self.is_subscription_expired()

    def subscription_days_left(self, today=None):
        """Số ngày còn lại của gói (0 = hết hạn cuối hôm nay, âm = đã hết hạn). None = không có ngày hết hạn."""
        if self.subscription_ends_on is None:
            return None
        today = today or timezone.localdate()
        return (self.subscription_ends_on - today).days

    def is_subscription_expired(self, today=None) -> bool:
        days_left = self.subscription_days_left(today)
        return days_left is not None and days_left < 0

    def dining_table_count(self) -> int:
        from App_Sales.models import DiningTable

        return DiningTable.objects.filter(tenant_id=self.pk).count()

    def staff_user_count(self) -> int:
        from App_Accounts.models import User

        return User.objects.filter(tenant_id=self.pk, role=User.Role.STAFF).count()

    def product_count(self) -> int:
        from App_Catalog.models import Product

        return Product.objects.filter(tenant_id=self.pk).count()

    @staticmethod
    def _within_limit(used: int, limit) -> bool:
        return limit is None or used < limit

    def can_create_store(self) -> bool:
        if not self.show_store_feature:
            return not self.stores.exists()
        return self._within_limit(self.stores.count(), self.max_stores)

    def can_create_dining_table(self) -> bool:
        return self._within_limit(self.dining_table_count(), self.max_dining_tables)

    def can_create_staff_user(self) -> bool:
        return self._within_limit(self.staff_user_count(), self.max_staff_users)

    def can_create_product(self) -> bool:
        return self._within_limit(self.product_count(), self.max_products)


class Store(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField('Số điện thoại', max_length=24, blank=True)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    is_default = models.BooleanField(default=False)
    payment_qr = models.ImageField(upload_to=store_payment_qr_upload_to, blank=True, null=True)
    payment_bank_name = models.CharField(max_length=120, blank=True)
    payment_account_name = models.CharField(max_length=120, blank=True)
    payment_account_number = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ['tenant__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uq_store_tenant_slug'),
            models.UniqueConstraint(
                fields=['tenant'],
                condition=Q(is_default=True),
                name='uq_default_store_per_tenant',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                prev = Store.objects.get(pk=self.pk)
            except Store.DoesNotExist:
                prev = None
            if prev and prev.payment_qr:
                old_name = prev.payment_qr.name
                new_name = self.payment_qr.name if self.payment_qr else ''
                if old_name and old_name != new_name:
                    prev.payment_qr.delete(save=False)
        self.slug = _build_unique_slug(
            Store.objects.filter(tenant_id=self.tenant_id).exclude(pk=self.pk),
            source_name=self.name,
            fallback='store',
        )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.payment_qr:
            self.payment_qr.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.tenant.name} - {self.name}'


class UserStoreAccess(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_accesses')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='user_accesses')
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'store'], name='uq_user_store_access'),
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='uq_default_store_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'store']),
        ]

    def clean(self):
        if not self.user_id or not self.store_id:
            return
        if self.user.tenant_id != self.store.tenant_id:
            raise ValidationError('Cửa hàng phải cùng doanh nghiệp với tài khoản.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} -> {self.store.name}'

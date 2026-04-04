from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
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
    'static',
    'media',
    'favicon.ico',
}


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


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=150)
    public_slug = models.SlugField(max_length=120, unique=True, validators=[validate_public_slug])
    is_active = models.BooleanField('Đang hoạt động', default=True)
    max_stores = models.PositiveIntegerField(
        'Giới hạn cửa hàng',
        default=1,
        blank=True,
        help_text='Số cửa hàng tối đa. 0 = không giới hạn. Mặc định gói mới: 1.',
    )
    max_dining_tables = models.PositiveIntegerField(
        'Giới hạn bàn',
        default=12,
        blank=True,
        help_text='Tổng số bàn (QR/POS) tối đa. 0 = không giới hạn. Mặc định gói mới: 12.',
    )
    max_staff_users = models.PositiveIntegerField(
        'Giới hạn nhân viên',
        default=2,
        blank=True,
        help_text='Số tài khoản nhân viên (không tính quản lý). 0 = không giới hạn. Mặc định gói mới: 2.',
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
            if self.subscription_ends_on is None:
                self.subscription_ends_on = self.subscription_starts_on + timedelta(days=365)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def dining_table_count(self) -> int:
        from App_Sales.models import DiningTable

        return DiningTable.objects.filter(tenant_id=self.pk).count()

    def staff_user_count(self) -> int:
        from App_Accounts.models import User

        return User.objects.filter(tenant_id=self.pk, role=User.Role.STAFF).count()

    def can_create_store(self) -> bool:
        if self.max_stores == 0:
            return True
        return self.stores.count() < self.max_stores

    def can_create_dining_table(self) -> bool:
        if self.max_dining_tables == 0:
            return True
        return self.dining_table_count() < self.max_dining_tables

    def can_create_staff_user(self) -> bool:
        if self.max_staff_users == 0:
            return True
        return self.staff_user_count() < self.max_staff_users


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

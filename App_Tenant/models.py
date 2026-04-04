import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from App_Core.models import TimeStampedModel


def store_payment_qr_upload_to(instance, filename):
    """Lưu ảnh QR theo tenant: ``store_payment_qr/tenant_{id}/``."""
    tid = instance.tenant_id
    if not tid:
        tid = 'unknown'
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else 'png').lower()[:8]
    if ext not in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        ext = 'png'
    return f'store_payment_qr/tenant_{tid}/qr_{uuid.uuid4().hex}.{ext}'

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
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def clean(self):
        self.public_slug = (self.public_slug or '').strip().lower()
        validate_public_slug(self.public_slug)

    def __str__(self):
        return self.name


class Store(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
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
            raise ValidationError('Store phải cùng tenant với user.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} -> {self.store.name}'

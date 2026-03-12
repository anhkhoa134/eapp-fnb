from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from App_Core.models import TimeStampedModel


def _build_unique_slug(queryset, source_name, fallback='item'):
    base_slug = slugify(source_name) or fallback
    candidate = base_slug
    suffix = 2
    while queryset.filter(slug=candidate).exists():
        candidate = f'{base_slug}-{suffix}'
        suffix += 1
    return candidate


class Category(TimeStampedModel):
    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uq_category_tenant_slug'),
        ]
        ordering = ['name']

    def save(self, *args, **kwargs):
        self.slug = _build_unique_slug(
            Category.objects.filter(tenant_id=self.tenant_id).exclude(pk=self.pk),
            source_name=self.name,
            fallback='category',
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uq_product_tenant_slug'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'name']),
        ]
        ordering = ['name']

    def clean(self):
        if self.category and self.category.tenant_id != self.tenant_id:
            raise ValidationError('Category phải cùng tenant với sản phẩm.')

    def save(self, *args, **kwargs):
        self.slug = _build_unique_slug(
            Product.objects.filter(tenant_id=self.tenant_id).exclude(pk=self.pk),
            source_name=self.name,
            fallback='product',
        )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductUnit(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='units')
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    sku = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'name'], name='uq_product_unit_name'),
        ]
        ordering = ['display_order', 'id']

    def __str__(self):
        return f'{self.product.name} - {self.name}'


class StoreCategory(TimeStampedModel):
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='category_links')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='store_links')
    is_visible = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['store', 'category'], name='uq_store_category'),
        ]

    def clean(self):
        if self.store.tenant_id != self.category.tenant_id:
            raise ValidationError('Store và category phải cùng tenant.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StoreProduct(TimeStampedModel):
    store = models.ForeignKey('App_Tenant.Store', on_delete=models.CASCADE, related_name='product_links')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='store_links')
    is_available = models.BooleanField(default=True)
    custom_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['store', 'product'], name='uq_store_product'),
        ]
        indexes = [
            models.Index(fields=['store', 'is_available']),
        ]

    def clean(self):
        if self.store.tenant_id != self.product.tenant_id:
            raise ValidationError('Store và product phải cùng tenant.')
        if self.custom_price is not None and self.custom_price < Decimal('0'):
            raise ValidationError('Giá tùy chỉnh phải >= 0.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

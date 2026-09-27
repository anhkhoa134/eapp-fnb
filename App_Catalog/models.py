from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from App_Core.models import TimeStampedModel
from App_Core.tenant_media_paths import product_image_file_upload_to, product_image_thumbnail_upload_to


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
    is_active = models.BooleanField('Đang hoạt động', default=True)

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
    description = models.TextField('Mô tả', blank=True)
    image_url = models.URLField(blank=True)
    image_file = models.ImageField('Ảnh upload', upload_to=product_image_file_upload_to, blank=True)
    image_thumbnail = models.ImageField('Thumbnail', upload_to=product_image_thumbnail_upload_to, blank=True)
    is_active = models.BooleanField('Đang hoạt động', default=True)

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
        if not self.category_id:
            return
        if not self.tenant_id:
            # Không dùng key 'tenant': ModelForm quản lý (vd. ProductForm) thường không có field tenant.
            raise ValidationError('Sản phẩm phải thuộc một doanh nghiệp trước khi gán danh mục.')
        # So khớp tenant theo DB (tránh object category trong memory lệch tenant).
        cat_tenant_id = (
            Category.objects.filter(pk=self.category_id).values_list('tenant_id', flat=True).first()
        )
        if cat_tenant_id != self.tenant_id:
            raise ValidationError({'category': 'Danh mục phải cùng doanh nghiệp với sản phẩm.'})

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

    def get_catalog_image_url(self) -> str:
        """URL for grid/list: prefer small WebP, then uploaded main, then external URL."""
        if self.image_thumbnail:
            return self.image_thumbnail.url
        if self.image_file:
            return self.image_file.url
        return (self.image_url or '').strip()

    @property
    def catalog_image_url(self) -> str:
        return self.get_catalog_image_url()

    def get_detail_image_url(self) -> str:
        """URL for larger view: full upload, then external URL."""
        if self.image_file:
            return self.image_file.url
        return (self.image_url or '').strip()

    def delete(self, *args, **kwargs):
        from App_Catalog.product_image_utils import clear_product_uploaded_images

        clear_product_uploaded_images(self)
        super().delete(*args, **kwargs)


class ProductUnit(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='units')
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    sku = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'name'], name='uq_product_unit_name'),
        ]
        ordering = ['display_order', 'id']

    def __str__(self):
        return f'{self.product.name} - {self.name}'


class Topping(TimeStampedModel):
    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='toppings')
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uq_topping_tenant_slug'),
        ]
        ordering = ['display_order', 'name', 'id']

    def save(self, *args, **kwargs):
        self.slug = _build_unique_slug(
            Topping.objects.filter(tenant_id=self.tenant_id).exclude(pk=self.pk),
            source_name=self.name,
            fallback='topping',
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductTopping(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='topping_links')
    topping = models.ForeignKey(Topping, on_delete=models.CASCADE, related_name='product_links')
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'topping'], name='uq_product_topping'),
        ]
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['topping', 'is_active']),
        ]
        ordering = ['display_order', 'id']

    def clean(self):
        # Let field-level validation surface required errors first.
        if not self.product_id or not self.topping_id:
            return
        if self.product.tenant_id != self.topping.tenant_id:
            raise ValidationError('Sản phẩm và topping phải cùng doanh nghiệp.')
        if self.price < Decimal('0'):
            raise ValidationError('Giá topping phải >= 0.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
            raise ValidationError('Cửa hàng và danh mục phải cùng doanh nghiệp.')

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
            raise ValidationError('Cửa hàng và sản phẩm phải cùng doanh nghiệp.')
        if self.custom_price is not None and self.custom_price < Decimal('0'):
            raise ValidationError('Giá tùy chỉnh phải >= 0.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Ingredient(TimeStampedModel):
    """Nguyên liệu dùng để pha chế / chế biến; giá vốn tính theo đơn vị tính."""

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField('Tên nguyên liệu', max_length=120)
    unit = models.CharField('Đơn vị tính', max_length=20)
    cost_per_unit = models.DecimalField('Giá vốn / đơn vị', max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField('Đang hoạt động', default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='uq_ingredient_tenant_name'),
        ]
        ordering = ['display_order', 'name', 'id']
        verbose_name = 'Nguyên liệu'
        verbose_name_plural = 'Nguyên liệu'

    def clean(self):
        if self.cost_per_unit is not None and self.cost_per_unit < Decimal('0'):
            raise ValidationError({'cost_per_unit': 'Giá vốn phải >= 0.'})

    def __str__(self):
        return f'{self.name} ({self.unit})'


class RecipeItem(TimeStampedModel):
    """Định mức: lượng nguyên liệu cho 1 thành phẩm (1 đơn vị bán của món, hoặc 1 phần topping)."""

    product_unit = models.ForeignKey(
        ProductUnit, on_delete=models.CASCADE, null=True, blank=True, related_name='recipe_items'
    )
    topping = models.ForeignKey(Topping, on_delete=models.CASCADE, null=True, blank=True, related_name='recipe_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='recipe_items')
    quantity = models.DecimalField('Định mức', max_digits=12, decimal_places=3)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(product_unit__isnull=False, topping__isnull=True)
                    | models.Q(product_unit__isnull=True, topping__isnull=False)
                ),
                name='ck_recipe_item_single_target',
            ),
            models.UniqueConstraint(
                fields=['product_unit', 'ingredient'],
                condition=models.Q(product_unit__isnull=False),
                name='uq_recipe_unit_ingredient',
            ),
            models.UniqueConstraint(
                fields=['topping', 'ingredient'],
                condition=models.Q(topping__isnull=False),
                name='uq_recipe_topping_ingredient',
            ),
        ]
        ordering = ['id']
        verbose_name = 'Định mức nguyên liệu'
        verbose_name_plural = 'Định mức nguyên liệu'

    def clean(self):
        super().clean()
        if isinstance(self.quantity, Decimal) and self.quantity.is_finite() and self.quantity <= 0:
            raise ValidationError({'quantity': 'Định mức phải lớn hơn 0.'})
        if self.ingredient_id:
            tenant_id = self.ingredient.tenant_id
            if self.product_unit_id and self.product_unit.product.tenant_id != tenant_id:
                raise ValidationError({'ingredient': 'Nguyên liệu và thành phẩm phải cùng doanh nghiệp.'})
            if self.topping_id and self.topping.tenant_id != tenant_id:
                raise ValidationError({'ingredient': 'Nguyên liệu và topping phải cùng doanh nghiệp.'})

    @property
    def cost(self) -> Decimal:
        return self.quantity * self.ingredient.cost_per_unit

    def __str__(self):
        target = self.product_unit or self.topping
        return f'{target}: {self.quantity} {self.ingredient.unit} {self.ingredient.name}'

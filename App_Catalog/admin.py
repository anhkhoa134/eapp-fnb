from django import forms
from django.contrib import admin
from django.utils.text import slugify

from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Tenant.models import Store


def _build_unique_slug(queryset, base_slug):
    candidate = base_slug
    suffix = 2
    while queryset.filter(slug=candidate).exists():
        candidate = f'{base_slug}-{suffix}'
        suffix += 1
    return candidate


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên danh mục.'
        self.fields['slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'

    def clean_slug(self):
        raw_value = (self.cleaned_data.get('slug') or '').strip().lower()
        base_slug = raw_value or (slugify(self.cleaned_data.get('name') or '') or 'category')
        tenant = self.cleaned_data.get('tenant') or getattr(self.instance, 'tenant', None)

        queryset = Category.objects.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        return _build_unique_slug(queryset=queryset, base_slug=base_slug)


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên sản phẩm.'
        self.fields['slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'

        tenant_id = None
        if self.instance.pk and self.instance.tenant_id:
            tenant_id = self.instance.tenant_id
        elif self.data is not None:
            tid = self.data.get('tenant')
            if tid not in (None, ''):
                tenant_id = tid
        if tenant_id is not None:
            self.fields['category'].queryset = Category.objects.filter(tenant_id=tenant_id).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        tenant = cleaned_data.get('tenant')
        category = cleaned_data.get('category')
        if tenant and category and category.tenant_id != tenant.id:
            self.add_error(
                'category',
                'Danh mục phải thuộc cùng doanh nghiệp với sản phẩm (chọn doanh nghiệp trước, chỉ chọn danh mục của doanh nghiệp đó).',
            )
        return cleaned_data

    def clean_slug(self):
        raw_value = (self.cleaned_data.get('slug') or '').strip().lower()
        base_slug = raw_value or (slugify(self.cleaned_data.get('name') or '') or 'product')
        tenant = self.cleaned_data.get('tenant') or getattr(self.instance, 'tenant', None)

        queryset = Product.objects.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        return _build_unique_slug(queryset=queryset, base_slug=base_slug)


class ToppingAdminForm(forms.ModelForm):
    class Meta:
        model = Topping
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Để trống thì hệ thống tự động tạo từ tên topping.'
        self.fields['slug'].widget.attrs['placeholder'] = 'Để trống thì tự động tạo'

    def clean_slug(self):
        raw_value = (self.cleaned_data.get('slug') or '').strip().lower()
        base_slug = raw_value or (slugify(self.cleaned_data.get('name') or '') or 'topping')
        tenant = self.cleaned_data.get('tenant') or getattr(self.instance, 'tenant', None)

        queryset = Topping.objects.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        return _build_unique_slug(queryset=queryset, base_slug=base_slug)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


class ProductUnitInline(admin.TabularInline):
    model = ProductUnit
    extra = 0


class ProductToppingInline(admin.TabularInline):
    model = ProductTopping
    extra = 0

    def get_formset(self, request, obj=None, **kwargs):
        self._parent_product_for_inline = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'topping':
            parent = getattr(self, '_parent_product_for_inline', None)
            tid = getattr(parent, 'tenant_id', None) if parent else None
            if tid:
                kwargs['queryset'] = Topping.objects.filter(tenant_id=tid).order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class StoreCategoryAdminForm(forms.ModelForm):
    class Meta:
        model = StoreCategory
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk:
            if self.instance.store_id:
                tenant_id = self.instance.store.tenant_id
            elif self.instance.category_id:
                tenant_id = self.instance.category.tenant_id
        elif self.data is not None:
            sid = self.data.get('store')
            cid = self.data.get('category')
            if sid:
                tenant_id = Store.objects.filter(pk=sid).values_list('tenant_id', flat=True).first()
            elif cid:
                tenant_id = Category.objects.filter(pk=cid).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['category'].queryset = Category.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        store = cleaned_data.get('store')
        category = cleaned_data.get('category')
        if store and category and store.tenant_id != category.tenant_id:
            self.add_error('category', 'Danh mục phải cùng doanh nghiệp với cửa hàng.')
        return cleaned_data


class StoreProductAdminForm(forms.ModelForm):
    class Meta:
        model = StoreProduct
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk:
            if self.instance.store_id:
                tenant_id = self.instance.store.tenant_id
            elif self.instance.product_id:
                tenant_id = self.instance.product.tenant_id
        elif self.data is not None:
            sid = self.data.get('store')
            pid = self.data.get('product')
            if sid:
                tenant_id = Store.objects.filter(pk=sid).values_list('tenant_id', flat=True).first()
            elif pid:
                tenant_id = Product.objects.filter(pk=pid).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['store'].queryset = Store.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['product'].queryset = Product.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        store = cleaned_data.get('store')
        product = cleaned_data.get('product')
        if store and product and store.tenant_id != product.tenant_id:
            self.add_error('product', 'Sản phẩm phải cùng doanh nghiệp với cửa hàng.')
        return cleaned_data


class ProductToppingAdminForm(forms.ModelForm):
    class Meta:
        model = ProductTopping
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = None
        if self.instance.pk:
            if self.instance.product_id:
                tenant_id = self.instance.product.tenant_id
            elif self.instance.topping_id:
                tenant_id = self.instance.topping.tenant_id
        elif self.data is not None:
            pid = self.data.get('product')
            tid = self.data.get('topping')
            if pid:
                tenant_id = Product.objects.filter(pk=pid).values_list('tenant_id', flat=True).first()
            elif tid:
                tenant_id = Topping.objects.filter(pk=tid).values_list('tenant_id', flat=True).first()
        if tenant_id is not None:
            self.fields['product'].queryset = Product.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')
            self.fields['topping'].queryset = Topping.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        topping = cleaned_data.get('topping')
        if product and topping and product.tenant_id != topping.tenant_id:
            self.add_error('topping', 'Topping phải cùng doanh nghiệp với sản phẩm.')
        return cleaned_data


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ('name', 'tenant', 'category', 'is_active')
    list_filter = ('tenant', 'is_active', 'category')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductUnitInline, ProductToppingInline]


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    form = StoreCategoryAdminForm
    list_display = ('store', 'category', 'is_visible')
    list_filter = ('store__tenant', 'is_visible')


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    form = StoreProductAdminForm
    list_display = ('store', 'product', 'is_available', 'custom_price')
    list_filter = ('store__tenant', 'is_available')


@admin.register(Topping)
class ToppingAdmin(admin.ModelAdmin):
    form = ToppingAdminForm
    list_display = ('name', 'tenant', 'is_active', 'display_order')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductTopping)
class ProductToppingAdmin(admin.ModelAdmin):
    form = ProductToppingAdminForm
    list_display = ('product', 'topping', 'price', 'is_active', 'display_order')
    list_filter = ('product__tenant', 'is_active')
    search_fields = ('product__name', 'topping__name')

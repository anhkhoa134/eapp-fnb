from django import forms
from django.contrib import admin
from django.utils.text import slugify

from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping


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
    list_display = ('store', 'category', 'is_visible')
    list_filter = ('store__tenant', 'is_visible')


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
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
    list_display = ('product', 'topping', 'price', 'is_active', 'display_order')
    list_filter = ('product__tenant', 'is_active')
    search_fields = ('product__name', 'topping__name')

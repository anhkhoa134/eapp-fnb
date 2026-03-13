from django.contrib import admin

from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name',)


class ProductUnitInline(admin.TabularInline):
    model = ProductUnit
    extra = 0


class ProductToppingInline(admin.TabularInline):
    model = ProductTopping
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'category', 'is_active')
    list_filter = ('tenant', 'is_active', 'category')
    search_fields = ('name',)
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
    list_display = ('name', 'tenant', 'is_active', 'display_order')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name',)


@admin.register(ProductTopping)
class ProductToppingAdmin(admin.ModelAdmin):
    list_display = ('product', 'topping', 'price', 'is_active', 'display_order')
    list_filter = ('product__tenant', 'is_active')
    search_fields = ('product__name', 'topping__name')

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils.text import slugify

from App_Catalog.admin import CategoryAdmin, CategoryAdminForm, ProductAdmin, ProductAdminForm, ToppingAdmin, ToppingAdminForm
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, Topping
from App_Tenant.models import Tenant


class ProductToppingModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo-catalog')
        self.category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        self.product = Product.objects.create(tenant=self.tenant, category=self.category, name='Nước ép')
        self.unit = ProductUnit.objects.create(product=self.product, name='M', price=Decimal('30000'))
        self.topping = Topping.objects.create(tenant=self.tenant, name='Thêm thạch')

    def test_product_topping_unique_constraint(self):
        ProductTopping.objects.create(product=self.product, topping=self.topping, price=Decimal('5000'))
        with self.assertRaises(ValidationError):
            ProductTopping.objects.create(product=self.product, topping=self.topping, price=Decimal('7000'))

    def test_product_topping_rejects_cross_tenant(self):
        other_tenant = Tenant.objects.create(name='Other', public_slug='other-catalog')
        other_topping = Topping.objects.create(tenant=other_tenant, name='Topping khác tenant')
        with self.assertRaises(ValidationError):
            ProductTopping.objects.create(product=self.product, topping=other_topping, price=Decimal('4000'))


class CatalogAdminSlugAutofillTests(TestCase):
    def test_category_product_topping_slug_autofill_configured(self):
        admin_site = AdminSite()
        category_admin = CategoryAdmin(Category, admin_site)
        product_admin = ProductAdmin(Product, admin_site)
        topping_admin = ToppingAdmin(Topping, admin_site)

        self.assertEqual(category_admin.prepopulated_fields, {'slug': ('name',)})
        self.assertEqual(product_admin.prepopulated_fields, {'slug': ('name',)})
        self.assertEqual(topping_admin.prepopulated_fields, {'slug': ('name',)})

    def test_category_form_blank_slug_auto_generates_unique_value(self):
        tenant = Tenant.objects.create(name='Catalog Tenant', public_slug='catalog-tenant')
        category_name = 'Đồ ăn'
        Category.objects.create(tenant=tenant, name=category_name)
        form = CategoryAdminForm(
            data={
                'tenant': tenant.id,
                'name': category_name,
                'slug': '',
                'description': '',
                'is_active': True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['slug'], f'{slugify(category_name)}-2')
        self.assertFalse(form.fields['slug'].required)
        self.assertIn('Để trống', form.fields['slug'].help_text)

    def test_product_form_blank_slug_auto_generates_unique_value(self):
        tenant = Tenant.objects.create(name='Product Tenant', public_slug='product-tenant')
        product_name = 'Cà phê Sữa đá'
        Product.objects.create(tenant=tenant, name=product_name)
        form = ProductAdminForm(
            data={
                'tenant': tenant.id,
                'category': '',
                'name': product_name,
                'slug': '',
                'description': '',
                'image_url': '',
                'is_active': True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['slug'], f'{slugify(product_name)}-2')
        self.assertFalse(form.fields['slug'].required)
        self.assertIn('Để trống', form.fields['slug'].help_text)

    def test_topping_form_blank_slug_auto_generates_unique_value(self):
        tenant = Tenant.objects.create(name='Topping Tenant', public_slug='topping-tenant')
        Topping.objects.create(tenant=tenant, name='Trân châu trắng')
        form = ToppingAdminForm(
            data={
                'tenant': tenant.id,
                'name': 'Trân châu trắng',
                'slug': '',
                'is_active': True,
                'display_order': 1,
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['slug'], 'tran-chau-trang-2')
        self.assertFalse(form.fields['slug'].required)
        self.assertIn('Để trống', form.fields['slug'].help_text)

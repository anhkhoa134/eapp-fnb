from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

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

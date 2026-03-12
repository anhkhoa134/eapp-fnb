import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import Order
from App_Tenant.models import Store, Tenant, UserStoreAccess


class SalesApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        self.store_1 = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.store_2 = Store.objects.create(tenant=self.tenant, name='Store 2', is_default=False)

        self.staff = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store_1, is_default=True)

        self.category = Category.objects.create(tenant=self.tenant, name='Đồ ăn')
        StoreCategory.objects.create(store=self.store_1, category=self.category, is_visible=True)
        StoreCategory.objects.create(store=self.store_2, category=self.category, is_visible=True)

        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name='Bánh mì',
            image_url='https://placehold.co/600x600/png?text=Banh+mi',
        )
        self.unit = ProductUnit.objects.create(product=self.product, name='Phần', price=Decimal('25000'))

        StoreProduct.objects.create(store=self.store_1, product=self.product, is_available=True)
        StoreProduct.objects.create(store=self.store_2, product=self.product, is_available=False)

        self.client.login(username='staff_demo', password='123456')

    def test_api_products_only_accessible_store(self):
        url = reverse('App_Sales_API:products')
        res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload['store']['id'], self.store_1.id)
        self.assertEqual(len(payload['products']), 1)

    def test_api_products_forbidden_unassigned_store(self):
        url = reverse('App_Sales_API:products')
        res = self.client.get(url, {'store_id': self.store_2.id})
        self.assertEqual(res.status_code, 403)

    def test_checkout_creates_order_and_items(self):
        url = reverse('App_Sales_API:checkout')
        payload = {
            'store_id': self.store_1.id,
            'payment_method': 'cash',
            'tax_rate': '0',
            'customer_paid': '30000',
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'note': 'Ít ớt',
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.total_amount, Decimal('25000'))
        self.assertEqual(order.items.count(), 1)

    def test_checkout_forbidden_unassigned_store(self):
        url = reverse('App_Sales_API:checkout')
        payload = {
            'store_id': self.store_2.id,
            'payment_method': 'cash',
            'tax_rate': '0',
            'customer_paid': '30000',
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 403)

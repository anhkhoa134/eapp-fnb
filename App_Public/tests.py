import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable, QROrder
from App_Tenant.models import Store, Tenant, UserStoreAccess


class RoutingAndPublicTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.user = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.user, store=self.store, is_default=True)

    def test_root_requires_login(self):
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/accounts/login/', res.url)

    def test_public_slug_route_works(self):
        res = self.client.get(reverse('App_Public:tenant_catalog', kwargs={'public_slug': 'demo'}))
        self.assertEqual(res.status_code, 200)

    def test_root_after_login_renders_pos(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('id=\"product-container\"', res.content.decode('utf-8'))

    def test_quanly_route_not_captured_by_public_slug(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get('/quanly/')
        self.assertEqual(res.status_code, 403)


class PublicQrApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo QR', public_slug='demo-qr')
        self.store = Store.objects.create(tenant=self.tenant, name='Store QR', is_default=True)
        self.category = Category.objects.create(tenant=self.tenant, name='Nước uống')
        StoreCategory.objects.create(store=self.store, category=self.category, is_visible=True)

        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name='Trà đào',
            image_url='https://placehold.co/600x600/png?text=Tra+dao',
        )
        self.unit = ProductUnit.objects.create(product=self.product, name='M', price=Decimal('39000'))
        StoreProduct.objects.create(store=self.store, product=self.product, is_available=True)

        self.table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store,
            code='QR-01',
            name='Bàn QR 01',
            qr_token='token-qr-01',
            is_active=True,
            display_order=1,
        )

    def test_public_qr_create_pending_order_success(self):
        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': 'qr-01',
            'token': 'token-qr-01',
            'note': 'Gọi thêm đá riêng',
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 2,
                    'note': 'Ít đá',
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(QROrder.objects.count(), 1)

        order = QROrder.objects.prefetch_related('items').first()
        self.assertEqual(order.status, QROrder.Status.PENDING)
        self.assertEqual(order.table_id, self.table.id)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.items.first().line_total, Decimal('78000'))

    def test_public_qr_wrong_token_returns_403(self):
        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': 'bad-token',
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
        self.assertEqual(QROrder.objects.count(), 0)

    def test_public_qr_rejects_unavailable_product(self):
        StoreProduct.objects.filter(store=self.store, product=self.product).update(is_available=False)

        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QROrder.objects.count(), 0)

    def test_public_qr_rejects_invalid_quantity(self):
        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 0,
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QROrder.objects.count(), 0)

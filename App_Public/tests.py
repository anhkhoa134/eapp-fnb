import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Sales.models import DiningTable, QROrder, QROrderItemTopping
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

    def test_public_qr_route_works(self):
        table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store,
            code='QR-DEMO',
            name='Bàn Demo',
            qr_token='demo-token',
            is_active=True,
            display_order=1,
        )
        res = self.client.get(
            reverse('App_Public:tenant_qr_ordering', kwargs={'public_slug': 'demo'}),
            {'table_code': table.code, 'token': table.qr_token},
        )
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('Gọi món QR', html)
        self.assertIn('qr-bootstrap-data', html)

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
        self.topping = Topping.objects.create(tenant=self.tenant, name='Thêm thạch')
        ProductTopping.objects.create(product=self.product, topping=self.topping, price=Decimal('8000'), is_active=True)

        self.table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store,
            code='QR-01',
            name='Bàn QR 01',
            qr_token='token-qr-01',
            is_active=True,
            display_order=1,
        )

    def _create_pending_order(self, note='Gọi thêm đá riêng'):
        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'note': note,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 2,
                    'note': 'Ít đá',
                    'topping_ids': [self.topping.id],
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        return res.json()['qr_order_id']

    def test_public_qr_create_pending_order_success(self):
        order_id = self._create_pending_order()
        self.assertEqual(QROrder.objects.count(), 1)

        order = QROrder.objects.prefetch_related('items').first()
        self.assertEqual(order.id, order_id)
        self.assertEqual(order.status, QROrder.Status.PENDING)
        self.assertEqual(order.table_id, self.table.id)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.items.first().line_total, Decimal('94000'))
        self.assertEqual(QROrderItemTopping.objects.filter(qr_order_item=order.items.first()).count(), 1)

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

    def test_public_qr_get_order_detail_success(self):
        order_id = self._create_pending_order()
        url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': order_id})
        res = self.client.get(url, {'table_code': self.table.code, 'token': self.table.qr_token})
        self.assertEqual(res.status_code, 200)
        payload = res.json()['order']
        self.assertEqual(payload['id'], order_id)
        self.assertEqual(payload['status'], QROrder.Status.PENDING)
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['qty'], 2)

    def test_public_qr_get_order_detail_wrong_token_returns_403(self):
        order_id = self._create_pending_order()
        url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': order_id})
        res = self.client.get(url, {'table_code': self.table.code, 'token': 'wrong-token'})
        self.assertEqual(res.status_code, 403)

    def test_public_qr_patch_pending_order_success(self):
        order_id = self._create_pending_order()
        url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': order_id})
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'note': 'Đổi ghi chú đơn',
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'note': 'Không đá',
                    'topping_ids': [],
                }
            ],
        }
        res = self.client.patch(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        body = res.json()['order']
        self.assertEqual(body['status'], QROrder.Status.PENDING)
        self.assertEqual(body['customer_note'], 'Đổi ghi chú đơn')
        self.assertEqual(body['items'][0]['qty'], 1)
        self.assertEqual(body['items'][0]['topping_ids'], [])

    def test_public_qr_patch_terminal_order_returns_400(self):
        order_id = self._create_pending_order()
        QROrder.objects.filter(id=order_id).update(status=QROrder.Status.APPROVED)

        url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': order_id})
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
        res = self.client.patch(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_public_qr_cancel_pending_success_and_idempotent(self):
        order_id = self._create_pending_order()
        url = reverse('App_Public_API:qr_orders_cancel', kwargs={'order_id': order_id})
        payload = {'table_code': self.table.code, 'token': self.table.qr_token}

        first = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['order']['status'], QROrder.Status.CANCELLED)

        second = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['order']['status'], QROrder.Status.CANCELLED)

    def test_public_qr_cancel_approved_order_returns_400(self):
        order_id = self._create_pending_order()
        QROrder.objects.filter(id=order_id).update(status=QROrder.Status.APPROVED)
        url = reverse('App_Public_API:qr_orders_cancel', kwargs={'order_id': order_id})
        payload = {'table_code': self.table.code, 'token': self.table.qr_token}
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)

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

    def test_public_qr_rejects_invalid_topping_mapping(self):
        other_topping = Topping.objects.create(tenant=self.tenant, name='Topping sản phẩm khác')
        other_product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name='Trà khác',
            image_url='https://placehold.co/600x600/png?text=Tra+khac',
        )
        ProductTopping.objects.create(product=other_product, topping=other_topping, price=Decimal('5000'), is_active=True)

        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'topping_ids': [other_topping.id],
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QROrder.objects.count(), 0)

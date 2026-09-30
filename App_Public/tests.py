import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Sales.models import DiningTable, KitchenTicket, Order, QROrder, QROrderItemTopping
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
        self.assertIn('Bàn Demo', html)
        self.assertIn('order-bootstrap-data', html)
        self.assertNotIn('WebSocket (fallback', html)

    def test_public_qr_route_shows_unavailable_when_feature_disabled(self):
        self.tenant.show_qr_order_feature = False
        self.tenant.save(update_fields=['show_qr_order_feature', 'updated_at'])
        table = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store,
            code='QR-OFF',
            name='Bàn QR tắt',
            qr_token='off-token',
            is_active=True,
            display_order=1,
        )
        res = self.client.get(
            reverse('App_Public:tenant_qr_ordering', kwargs={'public_slug': 'demo'}),
            {'table_code': table.code, 'token': table.qr_token},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Quán tạm ngưng gọi món qua mã QR', res.content.decode('utf-8'))

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

    def _create_pending_order(self, note='Gọi thêm đá riêng', **request_headers):
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
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json', **request_headers)
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

    @override_settings(LOGIN_TRUST_X_REAL_IP=True)
    def test_public_qr_create_with_duplicate_proxy_ip(self):
        order_id = self._create_pending_order(HTTP_X_REAL_IP='203.0.113.5,203.0.113.5')
        order = QROrder.objects.get(pk=order_id)
        self.assertEqual(order.created_by_ip, '203.0.113.5')
        self.assertEqual(order.items.count(), 1)

    @override_settings(LOGIN_TRUST_X_REAL_IP=True)
    def test_public_qr_create_with_unusable_ip(self):
        order_id = self._create_pending_order(HTTP_X_REAL_IP='unknown', REMOTE_ADDR='')
        self.assertIsNone(QROrder.objects.get(pk=order_id).created_by_ip)

    def test_public_qr_rejects_create_when_qr_feature_disabled(self):
        self.tenant.show_qr_order_feature = False
        self.tenant.save(update_fields=['show_qr_order_feature', 'updated_at'])
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
        self.assertEqual(res.status_code, 403)
        self.assertEqual(QROrder.objects.count(), 0)

    def test_public_qr_rejects_topping_when_topping_feature_disabled(self):
        self.tenant.show_topping_feature = False
        self.tenant.save(update_fields=['show_topping_feature', 'updated_at'])
        url = reverse('App_Public_API:qr_orders_create')
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'topping_ids': [self.topping.id],
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QROrder.objects.count(), 0)

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

    def test_public_qr_rejects_patch_when_qr_feature_disabled(self):
        order_id = self._create_pending_order()
        self.tenant.show_qr_order_feature = False
        self.tenant.save(update_fields=['show_qr_order_feature', 'updated_at'])
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
        self.assertEqual(res.status_code, 403)

    def test_public_qr_rejects_patch_empty_toppings_when_topping_feature_disabled(self):
        order_id = self._create_pending_order()
        self.tenant.show_topping_feature = False
        self.tenant.save(update_fields=['show_topping_feature', 'updated_at'])
        url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': order_id})
        payload = {
            'table_code': self.table.code,
            'token': self.table.qr_token,
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'topping_ids': [],
                }
            ],
        }
        res = self.client.patch(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QROrderItemTopping.objects.count(), 1)

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


class PublicTakeawayApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Mang Di', public_slug='demo-mang-di', show_kitchen_feature=True)
        self.store = Store.objects.create(tenant=self.tenant, name='Store MD', is_default=True)
        self.category = Category.objects.create(tenant=self.tenant, name='Cà phê')
        StoreCategory.objects.create(store=self.store, category=self.category, is_visible=True)
        self.product = Product.objects.create(tenant=self.tenant, category=self.category, name='Bạc xỉu')
        self.unit = ProductUnit.objects.create(product=self.product, name='L', price=Decimal('35000'))
        StoreProduct.objects.create(store=self.store, product=self.product, is_available=True)
        self.staff = User.objects.create_user(
            username='staff_md',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

    def _payload(self, **overrides):
        payload = {
            'tenant_slug': self.tenant.public_slug,
            'store_id': self.store.id,
            'customer_name': 'Chị Lan',
            'customer_phone': '0901 234 567',
            'note': 'Tới lấy lúc 9h',
            'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2}],
        }
        payload.update(overrides)
        return payload

    def _create(self, **overrides):
        return self.client.post(
            reverse('App_Public_API:takeaway_orders_create'),
            data=json.dumps(self._payload(**overrides)),
            content_type='application/json',
        )

    def test_catalog_page_enables_takeaway_ordering(self):
        res = self.client.get(reverse('App_Public:tenant_catalog', kwargs={'public_slug': self.tenant.public_slug}))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['ordering_enabled'])
        self.assertEqual(res.context['order_bootstrap_data']['mode'], 'takeaway')
        self.assertEqual(len(res.context['order_bootstrap_data']['products']), 1)

    def test_catalog_page_is_view_only_when_qr_feature_disabled(self):
        self.tenant.show_qr_order_feature = False
        self.tenant.save(update_fields=['show_qr_order_feature', 'updated_at'])
        res = self.client.get(reverse('App_Public:tenant_catalog', kwargs={'public_slug': self.tenant.public_slug}))
        self.assertFalse(res.context['ordering_enabled'])
        self.assertEqual(self._create().status_code, 403)

    def test_create_takeaway_order_without_table(self):
        res = self._create()
        self.assertEqual(res.status_code, 201)
        body = res.json()
        order = QROrder.objects.get(pk=body['qr_order_id'])
        self.assertIsNone(order.table_id)
        self.assertEqual(order.order_type, QROrder.OrderType.TAKEAWAY)
        self.assertEqual(order.customer_phone, '0901234567')
        self.assertEqual(body['access_key'], order.access_key)
        self.assertEqual(body['order']['total'], 70000.0)

    @override_settings(LOGIN_TRUST_X_REAL_IP=True)
    def test_create_takeaway_with_duplicate_proxy_ip(self):
        res = self.client.post(
            reverse('App_Public_API:takeaway_orders_create'),
            data=json.dumps(self._payload()),
            content_type='application/json',
            HTTP_X_REAL_IP='203.0.113.5,203.0.113.5',
        )
        self.assertEqual(res.status_code, 201)
        order = QROrder.objects.get(pk=res.json()['qr_order_id'])
        self.assertEqual(order.created_by_ip, '203.0.113.5')

    def test_create_takeaway_requires_valid_phone_and_name(self):
        self.assertEqual(self._create(customer_phone='12ab').status_code, 400)
        self.assertEqual(self._create(customer_name='  ').status_code, 400)
        self.assertFalse(QROrder.objects.exists())

    def test_takeaway_detail_and_cancel_require_access_key(self):
        body = self._create().json()
        detail_url = reverse('App_Public_API:qr_orders_detail', kwargs={'order_id': body['qr_order_id']})
        self.assertEqual(self.client.get(detail_url, {'access_key': 'wrong'}).status_code, 404)
        res = self.client.get(detail_url, {'access_key': body['access_key']})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['order']['customer_name'], 'Chị Lan')

        cancel_url = reverse('App_Public_API:qr_orders_cancel', kwargs={'order_id': body['qr_order_id']})
        res = self.client.post(
            cancel_url,
            data=json.dumps({'access_key': body['access_key']}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['order']['status'], QROrder.Status.CANCELLED)

    def test_takeaway_order_rate_limited_per_ip(self):
        from App_Public import views as public_views

        for _ in range(public_views.TAKEAWAY_ORDER_LIMIT_PER_IP):
            self.assertEqual(self._create().status_code, 201)
        self.assertEqual(self._create().status_code, 429)

    def test_pos_approve_sends_kitchen_then_checkout_links_order(self):
        order_id = self._create().json()['qr_order_id']
        self.client.force_login(self.staff)

        res = self.client.post(reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': order_id}))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['order_type'], QROrder.OrderType.TAKEAWAY)
        ticket = KitchenTicket.objects.get(qr_order_id=order_id)
        self.assertEqual(ticket.source, KitchenTicket.Source.TAKEAWAY)
        self.assertIn('Chị Lan', ticket.table_name)

        res = self.client.get(reverse('App_Sales_API:qr_orders'), {'store_id': self.store.id, 'status': 'awaiting_payment'})
        self.assertEqual([row['id'] for row in res.json()['orders']], [order_id])

        checkout_payload = {
            'store_id': self.store.id,
            'payment_method': 'cash',
            'customer_paid': 70000,
            'qr_order_id': order_id,
            'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2}],
        }
        res = self.client.post(
            reverse('App_Sales_API:checkout'),
            data=json.dumps(checkout_payload),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        sale = Order.objects.get(pk=res.json()['order_id'])
        self.assertEqual(QROrder.objects.get(pk=order_id).sale_order_id, sale.id)
        # Không tạo thêm phiếu bếp, chỉ gắn phiếu cũ với hoá đơn.
        self.assertEqual(KitchenTicket.objects.count(), 1)
        self.assertEqual(KitchenTicket.objects.get().order_id, sale.id)

        res = self.client.get(reverse('App_Sales_API:qr_orders'), {'store_id': self.store.id, 'status': 'awaiting_payment'})
        self.assertEqual(res.json()['orders'], [])

        # Thu tiền lần 2 cho cùng đơn bị chặn.
        res = self.client.post(
            reverse('App_Sales_API:checkout'),
            data=json.dumps(checkout_payload),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

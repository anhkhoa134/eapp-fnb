import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Sales.models import (
    DiningTable,
    Order,
    OrderItemTopping,
    QROrder,
    QROrderItem,
    QROrderItemTopping,
    TableCartItem,
    TableCartItemTopping,
)
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
        self.topping = Topping.objects.create(tenant=self.tenant, name='Trứng ốp la', is_active=True)
        self.product_topping = ProductTopping.objects.create(
            product=self.product,
            topping=self.topping,
            price=Decimal('6000'),
            is_active=True,
        )

        StoreProduct.objects.create(store=self.store_1, product=self.product, is_available=True)
        StoreProduct.objects.create(store=self.store_2, product=self.product, is_available=False)

        self.table_1 = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            code='S1-01',
            name='Bàn 01',
            display_order=1,
        )
        self.table_2 = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            code='S1-02',
            name='Bàn 02',
            display_order=2,
        )
        self.table_store_2 = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_2,
            code='S2-01',
            name='Bàn S2-01',
            display_order=1,
        )

        self.client.login(username='staff_demo', password='123456')

    def test_api_products_only_accessible_store(self):
        url = reverse('App_Sales_API:products')
        res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload['store']['id'], self.store_1.id)
        self.assertEqual(len(payload['products']), 1)

    def test_api_products_includes_store_payment_metadata(self):
        url = reverse('App_Sales_API:products')
        res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)
        store_payload = res.json()['store']
        self.assertIn('payment_qr_url', store_payload)
        self.assertIsNone(store_payload['payment_qr_url'])
        self.assertEqual(store_payload['payment_bank_name'], '')
        self.assertEqual(store_payload['payment_account_name'], '')
        self.assertEqual(store_payload['payment_account_number'], '')

        tiny_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05'
            b'\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        self.store_1.payment_qr = SimpleUploadedFile('qr.png', tiny_png, content_type='image/png')
        self.store_1.payment_bank_name = 'Vietcombank'
        self.store_1.payment_account_name = 'CUA HANG DEMO'
        self.store_1.payment_account_number = '0123456789'
        self.store_1.save()

        res2 = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res2.status_code, 200)
        store2 = res2.json()['store']
        self.assertTrue(store2['payment_qr_url'])
        self.assertIn(f'/media/tenant_{self.tenant.id}/store_payment_qr/', store2['payment_qr_url'])
        self.assertEqual(store2['payment_bank_name'], 'Vietcombank')
        self.assertEqual(store2['payment_account_name'], 'CUA HANG DEMO')
        self.assertEqual(store2['payment_account_number'], '0123456789')

    def test_api_products_returns_toppings_contract(self):
        url = reverse('App_Sales_API:products')
        res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertIn('categories', payload)
        self.assertEqual(payload['categories'][0]['name'], 'Tất cả')
        product_payload = payload['products'][0]
        self.assertIn('toppings', product_payload)
        self.assertEqual(product_payload['toppings'][0]['name'], self.topping.name)
        self.assertEqual(Decimal(str(product_payload['toppings'][0]['price'])), Decimal('6000'))

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
        self.assertEqual(order.sale_channel, Order.SaleChannel.TAKEAWAY)

    def test_checkout_with_toppings_creates_order_item_topping_snapshot(self):
        url = reverse('App_Sales_API:checkout')
        payload = {
            'store_id': self.store_1.id,
            'payment_method': 'cash',
            'tax_rate': '0',
            'customer_paid': '40000',
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 1,
                    'topping_ids': [self.topping.id],
                    'note': 'Thêm topping',
                }
            ],
        }
        res = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        order = Order.objects.first()
        self.assertEqual(order.total_amount, Decimal('31000'))
        order_item = order.items.first()
        self.assertEqual(OrderItemTopping.objects.filter(order_item=order_item).count(), 1)
        row = OrderItemTopping.objects.get(order_item=order_item)
        self.assertEqual(row.snapshot_topping_name, self.topping.name)
        self.assertEqual(row.snapshot_price, Decimal('6000'))

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

    def test_api_tables_returns_expected_statuses(self):
        TableCartItem.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_2,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=2,
            source=TableCartItem.Source.STAFF,
        )
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.PENDING,
            customer_note='Khách gọi món',
        )
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )

        url = reverse('App_Sales_API:tables')
        res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)

        table_payload = {row['id']: row for row in res.json()['tables']}
        self.assertEqual(table_payload[self.table_1.id]['status'], 'pending')
        self.assertEqual(table_payload[self.table_2.id]['status'], 'occupied')

    def test_table_cart_add_and_checkout_clears_cart(self):
        add_url = reverse('App_Sales_API:table_cart_add', kwargs={'table_id': self.table_1.id})
        add_payload = {
            'product_id': self.product.id,
            'unit_id': self.unit.id,
            'quantity': 2,
            'note': 'Không hành',
        }
        add_res = self.client.post(add_url, data=json.dumps(add_payload), content_type='application/json')
        self.assertEqual(add_res.status_code, 201)
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 1)

        checkout_url = reverse('App_Sales_API:table_checkout', kwargs={'table_id': self.table_1.id})
        checkout_payload = {
            'payment_method': 'cash',
            'tax_rate': 0,
            'customer_paid': 60000,
        }
        checkout_res = self.client.post(
            checkout_url,
            data=json.dumps(checkout_payload),
            content_type='application/json',
        )
        self.assertEqual(checkout_res.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.total_amount, Decimal('50000'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.sale_channel, Order.SaleChannel.DINE_IN)
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 0)

    def test_table_cart_add_with_toppings_snapshot(self):
        add_url = reverse('App_Sales_API:table_cart_add', kwargs={'table_id': self.table_1.id})
        add_payload = {
            'product_id': self.product.id,
            'unit_id': self.unit.id,
            'quantity': 1,
            'topping_ids': [self.topping.id],
            'note': 'No spicy',
        }
        add_res = self.client.post(add_url, data=json.dumps(add_payload), content_type='application/json')
        self.assertEqual(add_res.status_code, 201)
        item = TableCartItem.objects.get(table=self.table_1)
        self.assertEqual(item.unit_price_snapshot, Decimal('31000'))
        top = TableCartItemTopping.objects.get(table_cart_item=item)
        self.assertEqual(top.snapshot_topping_name, self.topping.name)
        self.assertEqual(top.snapshot_price, Decimal('6000'))

    def test_table_cart_patch_toppings_reprices_item(self):
        item = TableCartItem.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            source=TableCartItem.Source.STAFF,
        )
        patch_url = reverse(
            'App_Sales_API:table_cart_item',
            kwargs={'table_id': self.table_1.id, 'item_id': item.id},
        )
        patch_res = self.client.patch(
            patch_url,
            data=json.dumps({'topping_ids': [self.topping.id]}),
            content_type='application/json',
        )
        self.assertEqual(patch_res.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.unit_price_snapshot, Decimal('31000'))
        self.assertEqual(item.toppings.count(), 1)

    def test_table_cart_forbidden_unassigned_store(self):
        url = reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_store_2.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_table_import_takeaway_merges_toppings_into_table_cart(self):
        import_url = reverse('App_Sales_API:table_import_takeaway', kwargs={'table_id': self.table_1.id})
        payload = {
            'items': [
                {
                    'product_id': self.product.id,
                    'unit_id': self.unit.id,
                    'quantity': 2,
                    'note': 'Mang về rồi chuyển bàn',
                    'topping_ids': [self.topping.id],
                }
            ]
        }
        res = self.client.post(import_url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        item = TableCartItem.objects.get(table=self.table_1)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price_snapshot, Decimal('31000'))
        self.assertEqual(TableCartItemTopping.objects.filter(table_cart_item=item).count(), 1)

    def test_qr_approve_merges_into_table_cart_and_is_idempotent(self):
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.PENDING,
            customer_note='Đơn QR test',
        )
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=2,
            note='Ít đá',
            line_total=Decimal('0'),
        )

        approve_url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})
        first_res = self.client.post(approve_url, data='{}', content_type='application/json')
        self.assertEqual(first_res.status_code, 200)
        qr_order.refresh_from_db()
        self.assertEqual(qr_order.status, QROrder.Status.APPROVED)

        cart_items = TableCartItem.objects.filter(table=self.table_1, source=TableCartItem.Source.QR)
        self.assertEqual(cart_items.count(), 1)
        self.assertEqual(cart_items.first().quantity, 2)

        second_res = self.client.post(approve_url, data='{}', content_type='application/json')
        self.assertEqual(second_res.status_code, 200)
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1, source=TableCartItem.Source.QR).count(), 1)

    def test_qr_approve_keeps_item_toppings(self):
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.PENDING,
            customer_note='Đơn QR có topping',
        )
        qr_item = QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('31000'),
            quantity=1,
            line_total=Decimal('0'),
        )
        QROrderItemTopping.objects.create(
            qr_order_item=qr_item,
            topping=self.topping,
            snapshot_topping_name=self.topping.name,
            snapshot_price=Decimal('6000'),
        )

        approve_url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})
        first_res = self.client.post(approve_url, data='{}', content_type='application/json')
        self.assertEqual(first_res.status_code, 200)
        cart_item = TableCartItem.objects.get(table=self.table_1, source=TableCartItem.Source.QR)
        self.assertEqual(cart_item.unit_price_snapshot, Decimal('31000'))
        self.assertEqual(TableCartItemTopping.objects.filter(table_cart_item=cart_item).count(), 1)

    def test_qr_reject_does_not_create_table_cart_and_is_idempotent(self):
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.PENDING,
            customer_note='Đơn QR test reject',
        )
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )

        reject_url = reverse('App_Sales_API:qr_order_reject', kwargs={'order_id': qr_order.id})
        first_res = self.client.post(
            reject_url,
            data=json.dumps({'reason': 'Hết món'}),
            content_type='application/json',
        )
        self.assertEqual(first_res.status_code, 200)
        qr_order.refresh_from_db()
        self.assertEqual(qr_order.status, QROrder.Status.REJECTED)
        self.assertEqual(qr_order.rejection_reason, 'Hết món')
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 0)

        second_res = self.client.post(reject_url, data='{}', content_type='application/json')
        self.assertEqual(second_res.status_code, 200)

        approve_url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})
        approve_res = self.client.post(approve_url, data='{}', content_type='application/json')
        self.assertEqual(approve_res.status_code, 400)
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 0)

    def test_qr_approve_forbidden_unassigned_store(self):
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_2,
            table=self.table_store_2,
            status=QROrder.Status.PENDING,
            customer_note='Đơn QR store2',
        )
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )
        url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})
        res = self.client.post(url, data='{}', content_type='application/json')
        self.assertEqual(res.status_code, 403)
        qr_order.refresh_from_db()
        self.assertEqual(qr_order.status, QROrder.Status.PENDING)

    def test_qr_approve_or_reject_cancelled_order_returns_400(self):
        qr_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.CANCELLED,
            customer_note='Đơn QR đã bị khách hủy',
        )
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )

        approve_url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})
        reject_url = reverse('App_Sales_API:qr_order_reject', kwargs={'order_id': qr_order.id})

        approve_res = self.client.post(approve_url, data='{}', content_type='application/json')
        reject_res = self.client.post(reject_url, data='{}', content_type='application/json')

        self.assertEqual(approve_res.status_code, 400)
        self.assertEqual(reject_res.status_code, 400)
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 0)

    def test_qr_orders_pending_does_not_return_cancelled_orders(self):
        pending_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.PENDING,
            customer_note='Đơn pending',
        )
        cancelled_order = QROrder.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            table=self.table_1,
            status=QROrder.Status.CANCELLED,
            customer_note='Đơn cancelled',
        )
        QROrderItem.objects.create(
            qr_order=pending_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )
        QROrderItem.objects.create(
            qr_order=cancelled_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'),
            quantity=1,
            line_total=Decimal('0'),
        )

        url = reverse('App_Sales_API:qr_orders')
        res = self.client.get(url, {'store_id': self.store_1.id, 'status': 'pending'})
        self.assertEqual(res.status_code, 200)
        order_ids = [row['id'] for row in res.json()['orders']]
        self.assertIn(pending_order.id, order_ids)
        self.assertNotIn(cancelled_order.id, order_ids)

    def test_orders_today_page_staff_only_sees_accessible_store_orders(self):
        allow_order = Order.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            cashier=self.staff,
            payment_method=Order.PaymentMethod.CASH,
            subtotal=Decimal('25000'),
            tax_rate=Decimal('0'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('25000'),
            customer_paid=Decimal('30000'),
            change_amount=Decimal('5000'),
        )
        deny_order = Order.objects.create(
            tenant=self.tenant,
            store=self.store_2,
            cashier=self.staff,
            payment_method=Order.PaymentMethod.CASH,
            subtotal=Decimal('10000'),
            tax_rate=Decimal('0'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('10000'),
            customer_paid=Decimal('10000'),
            change_amount=Decimal('0'),
        )

        url = reverse('App_Sales:orders_today')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn(allow_order.order_code, html)
        self.assertNotIn(deny_order.order_code, html)

    def test_orders_today_page_manager_can_access(self):
        manager = User.objects.create_user(
            username='manager_today',
            password='123456',
            tenant=self.tenant,
            role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=manager, store=self.store_1, is_default=True)

        self.client.logout()
        self.client.login(username='manager_today', password='123456')
        res = self.client.get(reverse('App_Sales:orders_today'))
        self.assertEqual(res.status_code, 200)


class SalesModelTests(TestCase):
    def test_dining_table_unique_code_per_store(self):
        tenant = Tenant.objects.create(name='Tenant A', public_slug='tenant-a')
        store = Store.objects.create(tenant=tenant, name='Store A', is_default=True)
        DiningTable.objects.create(tenant=tenant, store=store, code='A-01', name='Bàn A-01')
        with self.assertRaises(ValidationError):
            DiningTable.objects.create(tenant=tenant, store=store, code='a-01', name='Bàn trùng mã')

    def test_table_cart_item_rejects_cross_tenant_data(self):
        tenant_1 = Tenant.objects.create(name='Tenant 1', public_slug='tenant-1')
        tenant_2 = Tenant.objects.create(name='Tenant 2', public_slug='tenant-2')
        store_1 = Store.objects.create(tenant=tenant_1, name='Store T1', is_default=True)
        store_2 = Store.objects.create(tenant=tenant_2, name='Store T2', is_default=True)
        table_1 = DiningTable.objects.create(tenant=tenant_1, store=store_1, code='T1-01', name='Bàn T1-01')

        with self.assertRaises(ValidationError):
            TableCartItem.objects.create(
                tenant=tenant_2,
                store=store_2,
                table=table_1,
                snapshot_product_name='Test',
                snapshot_unit_name='Đơn vị',
                unit_price_snapshot=Decimal('10000'),
                quantity=1,
            )


class PosJsIntegrationSmokeTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='POS JS', public_slug='pos-js')
        self.store_1 = Store.objects.create(tenant=self.tenant, name='Store A', is_default=True)
        self.store_2 = Store.objects.create(tenant=self.tenant, name='Store B', is_default=False)

        self.staff = User.objects.create_user(
            username='pos_staff',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store_1, is_default=True)
        UserStoreAccess.objects.create(user=self.staff, store=self.store_2, is_default=False)

        self.category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        StoreCategory.objects.create(store=self.store_1, category=self.category, is_visible=True)
        StoreCategory.objects.create(store=self.store_2, category=self.category, is_visible=True)

        self.product_a = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name='Nước A',
            image_url='https://placehold.co/600x600/png?text=Nuoc+A',
        )
        self.unit_a = ProductUnit.objects.create(product=self.product_a, name='M', price=Decimal('30000'))
        StoreProduct.objects.create(store=self.store_1, product=self.product_a, is_available=True)
        StoreProduct.objects.create(store=self.store_2, product=self.product_a, is_available=False)
        self.topping_a = Topping.objects.create(tenant=self.tenant, name='Topping A')
        ProductTopping.objects.create(product=self.product_a, topping=self.topping_a, price=Decimal('7000'), is_active=True)

        self.product_b = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name='Nước B',
            image_url='https://placehold.co/600x600/png?text=Nuoc+B',
        )
        self.unit_b = ProductUnit.objects.create(product=self.product_b, name='L', price=Decimal('42000'))
        StoreProduct.objects.create(store=self.store_1, product=self.product_b, is_available=False)
        StoreProduct.objects.create(store=self.store_2, product=self.product_b, is_available=True)

        self.table_a = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            code='A-01',
            name='Bàn A01',
            display_order=1,
        )
        self.table_b = DiningTable.objects.create(
            tenant=self.tenant,
            store=self.store_2,
            code='B-01',
            name='Bàn B01',
            display_order=1,
        )

        self.client.login(username='pos_staff', password='123456')

    def _create_pending_qr_order(self, *, table, product, unit, quantity=1, note=''):
        order = QROrder.objects.create(
            tenant=self.tenant,
            store=table.store,
            table=table,
            status=QROrder.Status.PENDING,
            customer_note='JS smoke order',
        )
        QROrderItem.objects.create(
            qr_order=order,
            product=product,
            unit=unit,
            snapshot_product_name=product.name,
            snapshot_unit_name=unit.name,
            unit_price_snapshot=unit.price,
            quantity=quantity,
            note=note,
            line_total=Decimal('0'),
        )
        return order

    def test_pos_page_contains_js_mount_points_and_api_symbols(self):
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')

        self.assertIn('id="product-container"', html)
        self.assertIn('id="tables-container"', html)
        self.assertIn('id="online-orders-container"', html)
        self.assertIn('id="storeSelector"', html)
        self.assertIn('id="tab-menu"', html)
        self.assertIn('id="tab-tables"', html)
        self.assertIn('id="tab-online"', html)
        self.assertIn('id="options-modal-toppings-container"', html)
        self.assertIn('id="payment-cash"', html)
        self.assertIn('id="payment-card"', html)
        self.assertIn('id="category-filter-container"', html)
        self.assertIn('id="themeSelector"', html)
        self.assertIn('Đơn hàng trong ngày', html)
        self.assertIn('Fullscreen', html)
        self.assertNotIn('Xin chào,', html)

        self.assertIn('const API_PRODUCTS_URL', html)
        self.assertIn('const API_TABLES_URL', html)
        self.assertIn('const API_QR_ORDERS_URL', html)
        self.assertIn('const renderCategoryFilters', html)
        self.assertIn('const toggleFullscreen', html)
        self.assertIn('cart/import-takeaway/', html)
        self.assertIn('topping_ids', html)
        self.assertIn('window.onload = () => {', html)

    def test_products_api_store_switch_contract(self):
        url = reverse('App_Sales_API:products')

        store_a_res = self.client.get(url, {'store_id': self.store_1.id})
        self.assertEqual(store_a_res.status_code, 200)
        store_a_payload = store_a_res.json()
        store_a_names = {row['name'] for row in store_a_payload['products']}
        self.assertEqual(store_a_names, {'Nước A'})
        self.assertIn('units', store_a_payload['products'][0])
        self.assertIn('id', store_a_payload['products'][0]['units'][0])
        self.assertIn('price', store_a_payload['products'][0]['units'][0])
        self.assertIn('categories', store_a_payload)
        self.assertIn('toppings', store_a_payload['products'][0])
        self.assertEqual(store_a_payload['products'][0]['toppings'][0]['id'], self.topping_a.id)
        self.assertEqual(store_a_payload['products'][0]['toppings'][0]['price'], 7000.0)

        store_b_res = self.client.get(url, {'store_id': self.store_2.id})
        self.assertEqual(store_b_res.status_code, 200)
        store_b_payload = store_b_res.json()
        store_b_names = {row['name'] for row in store_b_payload['products']}
        self.assertEqual(store_b_names, {'Nước B'})
        self.assertEqual(store_b_payload['products'][0]['toppings'], [])

    def test_js_contract_after_qr_approve_updates_online_and_table_cart(self):
        qr_order = self._create_pending_qr_order(
            table=self.table_a,
            product=self.product_a,
            unit=self.unit_a,
            quantity=2,
            note='Ít đá',
        )

        tables_url = reverse('App_Sales_API:tables')
        qr_orders_url = reverse('App_Sales_API:qr_orders')
        cart_url = reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_a.id})
        approve_url = reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id})

        before_tables = self.client.get(tables_url, {'store_id': self.store_1.id}).json()['tables']
        before_table_status = {row['id']: row['status'] for row in before_tables}[self.table_a.id]
        self.assertEqual(before_table_status, 'pending')

        before_orders = self.client.get(qr_orders_url, {'store_id': self.store_1.id, 'status': 'pending'}).json()['orders']
        self.assertEqual(len(before_orders), 1)

        approve_res = self.client.post(approve_url, data='{}', content_type='application/json')
        self.assertEqual(approve_res.status_code, 200)

        after_orders = self.client.get(qr_orders_url, {'store_id': self.store_1.id, 'status': 'pending'}).json()['orders']
        self.assertEqual(len(after_orders), 0)

        cart_payload = self.client.get(cart_url).json()
        self.assertEqual(len(cart_payload['items']), 1)
        self.assertEqual(cart_payload['items'][0]['source'], 'QR')
        self.assertEqual(cart_payload['items'][0]['qty'], 2)

        after_tables = self.client.get(tables_url, {'store_id': self.store_1.id}).json()['tables']
        after_table_status = {row['id']: row['status'] for row in after_tables}[self.table_a.id]
        self.assertEqual(after_table_status, 'occupied')

    def test_js_contract_after_qr_reject_keeps_table_empty(self):
        qr_order = self._create_pending_qr_order(
            table=self.table_a,
            product=self.product_a,
            unit=self.unit_a,
            quantity=1,
        )

        qr_orders_url = reverse('App_Sales_API:qr_orders')
        cart_url = reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_a.id})
        tables_url = reverse('App_Sales_API:tables')
        reject_url = reverse('App_Sales_API:qr_order_reject', kwargs={'order_id': qr_order.id})

        reject_res = self.client.post(
            reject_url,
            data=json.dumps({'reason': 'Kiểm thử từ chối'}),
            content_type='application/json',
        )
        self.assertEqual(reject_res.status_code, 200)

        pending_orders = self.client.get(qr_orders_url, {'store_id': self.store_1.id, 'status': 'pending'}).json()['orders']
        self.assertEqual(len(pending_orders), 0)

        cart_payload = self.client.get(cart_url).json()
        self.assertEqual(cart_payload['items'], [])

        table_rows = self.client.get(tables_url, {'store_id': self.store_1.id}).json()['tables']
        table_status = {row['id']: row['status'] for row in table_rows}[self.table_a.id]
        self.assertEqual(table_status, 'empty')

    def test_js_contract_after_table_checkout_clears_cart_and_status(self):
        add_url = reverse('App_Sales_API:table_cart_add', kwargs={'table_id': self.table_a.id})
        add_payload = {
            'product_id': self.product_a.id,
            'unit_id': self.unit_a.id,
            'quantity': 1,
            'note': 'Không đá',
        }
        add_res = self.client.post(add_url, data=json.dumps(add_payload), content_type='application/json')
        self.assertEqual(add_res.status_code, 201)

        checkout_url = reverse('App_Sales_API:table_checkout', kwargs={'table_id': self.table_a.id})
        checkout_payload = {
            'payment_method': 'cash',
            'tax_rate': 0,
            'customer_paid': 50000,
        }
        checkout_res = self.client.post(checkout_url, data=json.dumps(checkout_payload), content_type='application/json')
        self.assertEqual(checkout_res.status_code, 201)
        self.assertEqual(checkout_res.json()['table_status'], 'empty')

        cart_url = reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_a.id})
        cart_payload = self.client.get(cart_url).json()
        self.assertEqual(cart_payload['items'], [])

        tables_url = reverse('App_Sales_API:tables')
        table_rows = self.client.get(tables_url, {'store_id': self.store_1.id}).json()['tables']
        table_status = {row['id']: row['status'] for row in table_rows}[self.table_a.id]
        self.assertEqual(table_status, 'empty')

import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable, Order, QROrder, QROrderItem, TableCartItem
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
        self.assertEqual(TableCartItem.objects.filter(table=self.table_1).count(), 0)

    def test_table_cart_forbidden_unassigned_store(self):
        url = reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_store_2.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

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
        first_res = self.client.post(reject_url, data='{}', content_type='application/json')
        self.assertEqual(first_res.status_code, 200)
        qr_order.refresh_from_db()
        self.assertEqual(qr_order.status, QROrder.Status.REJECTED)
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

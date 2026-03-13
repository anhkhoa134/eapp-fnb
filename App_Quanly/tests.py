from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, Topping
from App_Sales.models import Order, OrderItem, OrderItemTopping
from App_Tenant.models import Store, Tenant, UserStoreAccess


class QuanlyPermissionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)

        self.manager = User.objects.create_user(
            username='manager_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.MANAGER,
        )
        self.staff = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

    def test_manager_can_access_dashboard(self):
        self.client.login(username='manager_demo', password='123456')
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get(reverse('App_Quanly:orders')).status_code, 200)

    def test_staff_cannot_access_dashboard(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Quanly:orders')).status_code, 403)

    def test_manager_can_access_topping_crud_pages(self):
        self.client.login(username='manager_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:toppings')).status_code, 200)
        redirect_res = self.client.get(reverse('App_Quanly:product_toppings'))
        self.assertEqual(redirect_res.status_code, 302)
        self.assertIn(reverse('App_Quanly:toppings'), redirect_res.url)

    def test_staff_cannot_access_topping_crud_pages(self):
        self.client.login(username='staff_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:toppings')).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Quanly:product_toppings')).status_code, 403)

    def test_manager_can_access_staff_management_pages(self):
        self.client.login(username='manager_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:staffs')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id})).status_code,
            200,
        )

    def test_staff_cannot_access_staff_management_pages(self):
        self.client.login(username='staff_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:staffs')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id})).status_code,
            403,
        )

    def test_manager_can_reset_staff_password(self):
        self.client.login(username='manager_demo', password='123456')
        res = self.client.post(
            reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id}),
            data={
                'new_password1': 'Reset@1234',
                'new_password2': 'Reset@1234',
            },
        )
        self.assertEqual(res.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password('Reset@1234'))


class QuanlyOrderHistoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Tenant Orders', public_slug='tenant-orders')
        self.store_1 = Store.objects.create(tenant=self.tenant, name='Store A', is_default=True)
        self.store_2 = Store.objects.create(tenant=self.tenant, name='Store B', is_default=False)

        self.manager = User.objects.create_user(
            username='manager_orders',
            password='123456',
            tenant=self.tenant,
            role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store_1, is_default=True)

        self.cashier_1 = User.objects.create_user(
            username='cashier_a',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        self.cashier_2 = User.objects.create_user(
            username='cashier_b',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.cashier_1, store=self.store_1, is_default=True)
        UserStoreAccess.objects.create(user=self.cashier_2, store=self.store_2, is_default=True)

        category = Category.objects.create(tenant=self.tenant, name='Đồ ăn')
        product = Product.objects.create(tenant=self.tenant, category=category, name='Phở Bò')
        unit = ProductUnit.objects.create(product=product, name='Thường', price=Decimal('90000'))
        topping = Topping.objects.create(tenant=self.tenant, name='Thêm trứng')

        self.order_1 = Order.objects.create(
            tenant=self.tenant,
            store=self.store_1,
            cashier=self.cashier_1,
            payment_method=Order.PaymentMethod.CASH,
            status=Order.Status.COMPLETED,
            subtotal=Decimal('100000'),
            tax_rate=Decimal('0'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('100000'),
            customer_paid=Decimal('120000'),
            change_amount=Decimal('20000'),
        )
        self.order_2 = Order.objects.create(
            tenant=self.tenant,
            store=self.store_2,
            cashier=self.cashier_2,
            payment_method=Order.PaymentMethod.CARD,
            status=Order.Status.CANCELLED,
            subtotal=Decimal('70000'),
            tax_rate=Decimal('0'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('70000'),
            customer_paid=Decimal('70000'),
            change_amount=Decimal('0'),
        )
        Order.objects.filter(pk=self.order_1.pk).update(created_at=timezone.now())
        Order.objects.filter(pk=self.order_2.pk).update(created_at=timezone.now() - timedelta(days=10))
        self.order_1.refresh_from_db()
        self.order_2.refresh_from_db()

        self.order_1.order_code = 'ORD-HISTORY-A'
        self.order_1.save(update_fields=['order_code'])
        self.order_2.order_code = 'ORD-HISTORY-B'
        self.order_2.save(update_fields=['order_code'])

        item = OrderItem.objects.create(
            order=self.order_1,
            product=product,
            unit=unit,
            snapshot_product_name='Phở Bò Kobe',
            snapshot_unit_name='Thường',
            unit_price=Decimal('95000'),
            quantity=1,
            note='Ít hành',
            line_total=Decimal('0'),
        )
        OrderItemTopping.objects.create(
            order_item=item,
            topping=topping,
            snapshot_topping_name='Thêm trứng',
            snapshot_price=Decimal('5000'),
        )

    def test_order_history_filters_work(self):
        self.client.login(username='manager_orders', password='123456')
        res = self.client.get(
            reverse('App_Quanly:orders'),
            {
                'store': str(self.store_1.id),
                'payment_method': Order.PaymentMethod.CASH,
                'status': Order.Status.COMPLETED,
                'cashier': str(self.cashier_1.id),
                'q': 'ORD-HISTORY-A',
                'date_from': (timezone.localdate() - timedelta(days=1)).isoformat(),
                'date_to': timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('ORD-HISTORY-A', html)
        self.assertNotIn('ORD-HISTORY-B', html)

    def test_order_history_pagination_keeps_query_params(self):
        self.client.login(username='manager_orders', password='123456')
        for idx in range(1, 23):
            order = Order.objects.create(
                tenant=self.tenant,
                store=self.store_1,
                cashier=self.cashier_1,
                payment_method=Order.PaymentMethod.CASH,
                status=Order.Status.COMPLETED,
                subtotal=Decimal('10000'),
                tax_rate=Decimal('0'),
                tax_amount=Decimal('0'),
                total_amount=Decimal('10000'),
                customer_paid=Decimal('10000'),
                change_amount=Decimal('0'),
            )
            order.order_code = f'ORD-PAGE-{idx:02d}'
            order.save(update_fields=['order_code'])

        res = self.client.get(reverse('App_Quanly:orders'), {'q': 'ORD-PAGE'})
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('?q=ORD-PAGE&page=2', html)

    def test_order_history_renders_item_and_topping_snapshot(self):
        self.client.login(username='manager_orders', password='123456')
        res = self.client.get(reverse('App_Quanly:orders'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('Phở Bò Kobe', html)
        self.assertIn('Thêm trứng', html)


class QuanlyToppingUnifiedFormTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Tenant Top', public_slug='tenant-top')
        self.store = Store.objects.create(tenant=self.tenant, name='Store Top', is_default=True)
        self.manager = User.objects.create_user(
            username='manager_top',
            password='123456',
            tenant=self.tenant,
            role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)

        category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        self.product = Product.objects.create(tenant=self.tenant, category=category, name='Cà phê sữa')
        self.topping = Topping.objects.create(tenant=self.tenant, name='Thêm sữa')

    def test_create_topping_form_type_topping_success(self):
        self.client.login(username='manager_top', password='123456')
        res = self.client.post(
            reverse('App_Quanly:toppings'),
            data={
                'form_type': 'topping',
                'topping-name': 'Thêm kem',
                'topping-display_order': '1',
                'topping-is_active': 'on',
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Topping.objects.filter(tenant=self.tenant, name='Thêm kem').exists())

    def test_create_mapping_form_type_mapping_success(self):
        self.client.login(username='manager_top', password='123456')
        res = self.client.post(
            reverse('App_Quanly:toppings'),
            data={
                'form_type': 'mapping',
                'mapping-product': str(self.product.id),
                'mapping-topping': str(self.topping.id),
                'mapping-price': '7000',
                'mapping-display_order': '0',
                'mapping-is_active': 'on',
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(ProductTopping.objects.filter(product=self.product, topping=self.topping).exists())

    def test_invalid_mapping_form_shows_error_message(self):
        self.client.login(username='manager_top', password='123456')
        res = self.client.post(
            reverse('App_Quanly:toppings'),
            data={
                'form_type': 'mapping',
                'mapping-price': '5000',
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Không thể gán topping cho sản phẩm, vui lòng kiểm tra dữ liệu.', res.content.decode('utf-8'))

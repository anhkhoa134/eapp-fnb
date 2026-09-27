import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Core.models import AuditLog
from App_Sales.models import DiningTable, KitchenTicket, Order, Refund, Shift, TableCartItem
from App_Sales.shifts import compute_shift_summary
from App_Tenant.models import Store, Tenant, UserStoreAccess


class OpsTestBase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Demo', public_slug='demo-ops', show_kitchen_feature=True, show_shift_feature=True
        )
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True, address='1 Lê Lợi')
        self.other_store = Store.objects.create(tenant=self.tenant, name='Store 2')

        self.staff = User.objects.create_user(
            username='ops_staff', password='123456', tenant=self.tenant, role=User.Role.STAFF
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)
        self.manager = User.objects.create_user(
            username='ops_manager', password='123456', tenant=self.tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        UserStoreAccess.objects.create(user=self.manager, store=self.other_store)

        category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        StoreCategory.objects.create(store=self.store, category=category, is_visible=True)
        self.product = Product.objects.create(tenant=self.tenant, category=category, name='Cà phê sữa')
        self.unit = ProductUnit.objects.create(product=self.product, name='Ly', price=Decimal('30000'))
        StoreProduct.objects.create(store=self.store, product=self.product, is_available=True)
        self.table = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='B01', name='Bàn 01')

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def checkout_takeaway(self, *, quantity=1, payment_method='cash', customer_paid='100000'):
        response = self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': payment_method,
                'customer_paid': customer_paid,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': quantity}],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Order.objects.get(pk=response.json()['order_id'])

    def add_to_table(self, quantity=2):
        response = self.post_json(
            reverse('App_Sales_API:table_cart_add', args=[self.table.id]),
            {'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': quantity},
        )
        self.assertIn(response.status_code, (200, 201), response.content)


class ReceiptPrintTests(OpsTestBase):
    def test_receipt_renders_and_counts_reprints(self):
        self.login(self.staff)
        order = self.checkout_takeaway(quantity=2)
        url = reverse('App_Sales:order_receipt', args=[order.id])

        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['X-Frame-Options'], 'SAMEORIGIN')
        self.assertContains(preview, order.order_code)
        self.assertContains(preview, 'Cà phê sữa')
        self.assertContains(preview, '60.000')
        self.assertNotContains(preview, 'BẢN IN LẠI')
        order.refresh_from_db()
        self.assertEqual(order.print_count, 0)

        first = self.client.get(url, {'autoprint': '1'})
        self.assertNotContains(first, 'BẢN IN LẠI')
        second = self.client.get(url, {'autoprint': '1'})
        self.assertContains(second, 'BẢN IN LẠI (lần 2)')
        order.refresh_from_db()
        self.assertEqual(order.print_count, 2)
        self.assertTrue(
            AuditLog.objects.filter(tenant=self.tenant, action=AuditLog.Action.ORDER_REPRINT, object_id=str(order.id)).exists()
        )

    def test_receipt_forbidden_for_store_without_access(self):
        self.login(self.manager)
        order = Order.objects.create(
            tenant=self.tenant,
            store=self.other_store,
            cashier=self.manager,
            payment_method=Order.PaymentMethod.CASH,
            subtotal=Decimal('30000'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('30000'),
            customer_paid=Decimal('30000'),
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse('App_Sales:order_receipt', args=[order.id]))
        self.assertEqual(response.status_code, 403)

    def test_table_checkout_keeps_table_name_on_receipt(self):
        self.login(self.staff)
        self.add_to_table(quantity=1)
        response = self.post_json(
            reverse('App_Sales_API:table_checkout', args=[self.table.id]),
            {'payment_method': 'card', 'customer_paid': 0},
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertIsNotNone(data['kitchen_ticket_id'])
        order = Order.objects.get(pk=data['order_id'])
        self.assertEqual(order.table_name, 'Bàn 01')
        receipt = self.client.get(reverse('App_Sales:order_receipt', args=[order.id]))
        self.assertContains(receipt, 'Bàn 01')

    def test_table_bill_lists_cart_and_subtotal(self):
        self.login(self.staff)
        self.add_to_table(quantity=3)
        response = self.client.get(reverse('App_Sales:table_bill', args=[self.table.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PHIẾU TẠM TÍNH')
        self.assertContains(response, '90.000')

    def test_kitchen_ticket_print(self):
        self.login(self.staff)
        self.add_to_table(quantity=2)
        response = self.post_json(reverse('App_Sales_API:table_kitchen_send', args=[self.table.id]), {})
        ticket_id = response.json()['ticket_id']
        url = reverse('App_Sales:kitchen_ticket_print', args=[ticket_id])
        self.client.get(url, {'autoprint': '1'})
        reprint = self.client.get(url, {'autoprint': '1'})
        self.assertContains(reprint, 'Bàn 01')
        self.assertContains(reprint, 'IN LẠI (lần 2)')
        self.assertEqual(KitchenTicket.objects.get(pk=ticket_id).print_count, 2)

        self.tenant.show_kitchen_feature = False
        self.tenant.save(update_fields=['show_kitchen_feature'])
        self.assertEqual(self.client.get(url).status_code, 403)


class ShiftTests(OpsTestBase):
    def test_open_close_shift_with_cash_reconciliation(self):
        self.login(self.staff)
        url = reverse('App_Sales:shifts')
        self.client.post(url, {'action': 'open', 'store_id': self.store.id, 'opening_cash': '500.000'})
        shift = Shift.objects.get(store=self.store)
        self.assertEqual(shift.opening_cash, Decimal('500000'))
        self.assertEqual(shift.status, Shift.Status.OPEN)

        current = self.client.get(reverse('App_Sales_API:shift_current'), {'store_id': self.store.id}).json()
        self.assertEqual(current['shift']['id'], shift.id)

        # Không mở được ca thứ hai cho cùng cửa hàng.
        self.client.post(url, {'action': 'open', 'store_id': self.store.id, 'opening_cash': '0'})
        self.assertEqual(Shift.objects.filter(store=self.store).count(), 1)

        cash_order = self.checkout_takeaway(quantity=2)  # 60.000 tiền mặt
        self.checkout_takeaway(quantity=1, payment_method='card', customer_paid='0')  # 30.000 thẻ
        Refund.objects.create(
            tenant=self.tenant,
            store=self.store,
            order=cash_order,
            amount=Decimal('10000'),
            method=Order.PaymentMethod.CASH,
            reason='test',
        )
        summary = compute_shift_summary(shift)
        self.assertEqual(summary['order_count'], 2)
        self.assertEqual(summary['gross_sales'], Decimal('90000'))
        self.assertEqual(summary['cash_sales'], Decimal('60000'))
        self.assertEqual(summary['card_sales'], Decimal('30000'))
        self.assertEqual(summary['expected_cash'], Decimal('550000'))

        page = self.client.get(url)
        self.assertContains(page, f'Ca #{shift.id} đang mở')

        response = self.client.post(
            url, {'action': 'close', 'store_id': self.store.id, 'counted_cash': '540.000', 'note': 'thiếu 10k'}
        )
        self.assertRedirects(response, f'{url}?store_id={self.store.id}&print_shift={shift.id}')
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertEqual(shift.expected_cash, Decimal('550000'))
        self.assertEqual(shift.counted_cash, Decimal('540000'))
        self.assertEqual(shift.cash_difference, Decimal('-10000'))
        self.assertEqual(shift.refund_total, Decimal('10000'))

        # Số liệu ca đã chốt không đổi khi có đơn mới.
        self.checkout_takeaway(quantity=1)
        report = self.client.get(reverse('App_Sales:shift_print', args=[shift.id]))
        self.assertContains(report, 'BÁO CÁO CHỐT CA')
        self.assertContains(report, '540.000')
        self.assertContains(report, '-10.000')

        self.assertTrue(AuditLog.objects.filter(tenant=self.tenant, action=AuditLog.Action.SHIFT_OPEN).exists())
        close_log = AuditLog.objects.get(tenant=self.tenant, action=AuditLog.Action.SHIFT_CLOSE)
        self.assertIn('dự kiến 550.000 đ, thực đếm 540.000 đ, chênh lệch -10.000 đ', close_log.message)

    def test_close_requires_counted_cash(self):
        self.login(self.staff)
        url = reverse('App_Sales:shifts')
        self.client.post(url, {'action': 'open', 'store_id': self.store.id, 'opening_cash': '0'})
        self.client.post(url, {'action': 'close', 'store_id': self.store.id, 'counted_cash': ''})
        self.assertEqual(Shift.objects.get(store=self.store).status, Shift.Status.OPEN)

    def test_shift_feature_toggle(self):
        self.login(self.manager)
        self.client.post(
            reverse('App_Sales:shifts'), {'action': 'open', 'store_id': self.store.id, 'opening_cash': '0'}
        )
        shift = Shift.objects.get(store=self.store)
        settings_page = self.client.get(reverse('App_Quanly:feature_settings'))
        self.assertContains(settings_page, 'Ca làm việc (chốt ca)')
        # Lối vào nằm trong nhóm con của "Cấu hình tính năng" ở sidebar.
        sidebar = settings_page.content.decode()
        subgroup = sidebar[sidebar.index('admin-nav-subgroup">'):]
        self.assertIn(reverse('App_Sales:shifts'), subgroup[: subgroup.index('</div>')])

        # Tắt ở Cấu hình tính năng -> khoá trang, API, bản in và ẩn lối vào.
        self.client.post(
            reverse('App_Quanly:feature_settings'), {'show_store_feature': 'on', 'show_kitchen_feature': 'on'}
        )
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.show_shift_feature)
        self.assertEqual(self.client.get(reverse('App_Sales:shifts')).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Sales:shift_print', args=[shift.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Sales_API:shift_current')).status_code, 403)
        self.assertNotContains(self.client.get(reverse('App_Sales:pos')), 'id="shiftMenuLink"')
        self.assertNotContains(self.client.get(reverse('App_Quanly:dashboard')), reverse('App_Sales:shifts'))
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant, action=AuditLog.Action.OBJECT_UPDATE, object_type='Doanh nghiệp'
            ).exists()
        )

        # Bật lại: ca đang mở vẫn còn nguyên.
        self.client.post(
            reverse('App_Quanly:feature_settings'),
            {'show_store_feature': 'on', 'show_kitchen_feature': 'on', 'show_shift_feature': 'on'},
        )
        self.assertContains(self.client.get(reverse('App_Sales:shifts')), f'Ca #{shift.id} đang mở')

    def test_shift_feature_follows_subscription_plan(self):
        from App_Tenant.models import SubscriptionPlan

        self.assertFalse(Tenant(name='Mới', public_slug='moi-ops').show_shift_feature)
        free = SubscriptionPlan.objects.get(slug='mien-phi')
        basic = SubscriptionPlan.objects.get(slug='co-ban')
        self.assertFalse(free.feature_shift)
        self.assertTrue(basic.feature_shift)

        self.tenant.apply_subscription_plan(free)
        self.tenant.save()
        self.assertFalse(self.tenant.show_shift_feature)
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse('App_Sales:shifts')).status_code, 403)
        # Gói Miễn phí: không bật được dù gửi form.
        self.client.post(
            reverse('App_Quanly:feature_settings'), {'show_store_feature': 'on', 'show_shift_feature': 'on'}
        )
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.show_shift_feature)
        self.assertContains(self.client.get(reverse('App_Quanly:feature_settings')), 'Cần nâng cấp gói')

        self.tenant.apply_subscription_plan(basic)
        self.tenant.save()
        self.client.post(
            reverse('App_Quanly:feature_settings'), {'show_store_feature': 'on', 'show_shift_feature': 'on'}
        )
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.show_shift_feature)
        self.assertEqual(self.client.get(reverse('App_Sales:shifts')).status_code, 200)

    def test_shifts_slug_is_reserved(self):
        from django.core.exceptions import ValidationError

        tenant = Tenant(name='X', public_slug='shifts')
        with self.assertRaises(ValidationError):
            tenant.full_clean()


class RefundTests(OpsTestBase):
    def refund(self, order, **data):
        payload = {'refund_type': 'full', 'reason': 'Món lỗi', 'method': 'cash', **data}
        return self.client.post(reverse('App_Quanly:order_refund', args=[order.id]), payload)

    def test_partial_then_full_refund(self):
        self.login(self.staff)
        order = self.checkout_takeaway(quantity=2)  # 60.000
        self.login(self.manager)

        self.refund(order, refund_type='partial', amount='20.000')
        order.refresh_from_db()
        self.assertEqual(order.refunded_amount, Decimal('20000'))
        self.assertEqual(order.status, Order.Status.COMPLETED)

        # Vượt số còn lại -> không hoàn.
        self.refund(order, refund_type='partial', amount='50.000')
        order.refresh_from_db()
        self.assertEqual(order.refunded_amount, Decimal('20000'))

        self.refund(order, refund_type='full')
        order.refresh_from_db()
        self.assertEqual(order.refunded_amount, Decimal('60000'))
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(order.refunds.count(), 2)
        refund_logs = AuditLog.objects.filter(tenant=self.tenant, action=AuditLog.Action.ORDER_REFUND)
        self.assertEqual(refund_logs.count(), 2)
        self.assertIn('Hoàn 20.000 đ (tiền mặt)', refund_logs.order_by('id').first().message)

        history = self.client.get(reverse('App_Quanly:orders'))
        self.assertContains(history, 'Đã hoàn tiền')

    def test_refund_requires_reason_and_manager(self):
        self.login(self.staff)
        order = self.checkout_takeaway()
        response = self.refund(order)
        self.assertEqual(response.status_code, 403)

        self.login(self.manager)
        self.refund(order, reason='  ')
        order.refresh_from_db()
        self.assertEqual(order.refunded_amount, Decimal('0'))

    def test_revenue_is_net_of_refunds(self):
        self.login(self.staff)
        order = self.checkout_takeaway(quantity=2)  # 60.000
        self.checkout_takeaway(quantity=1)  # 30.000
        self.login(self.manager)
        self.refund(order, refund_type='partial', amount='15000')

        today = self.client.get(reverse('App_Sales:orders_today'))
        self.assertEqual(today.context['total_revenue'], Decimal('75000'))
        history = self.client.get(reverse('App_Quanly:orders'))
        self.assertEqual(history.context['total_revenue'], Decimal('75000'))
        dashboard = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertContains(dashboard, '75.000')


class AuditLogTests(OpsTestBase):
    def test_cart_void_and_table_move_are_logged(self):
        self.login(self.staff)
        self.add_to_table(quantity=3)
        self.post_json(reverse('App_Sales_API:table_kitchen_send', args=[self.table.id]), {})
        item = TableCartItem.objects.get(table=self.table)
        self.client.patch(
            reverse('App_Sales_API:table_cart_item', args=[self.table.id, item.id]),
            data=json.dumps({'quantity': 1}),
            content_type='application/json',
        )
        log = AuditLog.objects.get(tenant=self.tenant, action=AuditLog.Action.CART_VOID)
        self.assertIn('Cà phê sữa x2', log.message)
        self.assertIn('đã báo bếp', log.message)
        self.assertEqual(log.username, 'ops_staff')

        table_2 = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='B02', name='Bàn 02')
        self.post_json(reverse('App_Sales_API:table_cart_move_to', args=[self.table.id]), {'to_table_id': table_2.id})
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.TABLE_MOVE, store=self.store).exists())

    def test_price_change_logged_with_diff(self):
        self.login(self.manager)
        self.client.post(
            reverse('App_Quanly:unit_edit', args=[self.unit.id]),
            {'name': 'Ly', 'price': '35000', 'sku': '', 'is_active': 'on'},
        )
        log = AuditLog.objects.get(tenant=self.tenant, action=AuditLog.Action.OBJECT_UPDATE)
        self.assertEqual(log.object_type, 'Đơn vị bán')
        self.assertEqual(log.extra['changes'], [{'field': 'Giá', 'old': '30.000', 'new': '35.000'}])

    def test_no_log_without_request_user(self):
        self.unit.price = Decimal('40000')
        self.unit.save()
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.OBJECT_UPDATE).exists())

    def test_login_and_failed_login_logged(self):
        self.client.post(reverse('App_Accounts:login'), {'username': 'ops_staff', 'password': 'wrong'})
        self.client.post(reverse('App_Accounts:login'), {'username': 'ops_staff', 'password': '123456'})
        actions = list(AuditLog.objects.filter(tenant=self.tenant).values_list('action', flat=True))
        self.assertIn(AuditLog.Action.LOGIN_FAILED, actions)
        self.assertIn(AuditLog.Action.LOGIN, actions)

    def test_audit_page_is_manager_only_and_tenant_scoped(self):
        other_tenant = Tenant.objects.create(name='Other', public_slug='other-ops')
        AuditLog.objects.create(tenant=other_tenant, action=AuditLog.Action.LOGIN, message='other tenant secret')
        AuditLog.objects.create(tenant=self.tenant, action=AuditLog.Action.LOGIN, message='own tenant entry')

        self.login(self.staff)
        self.assertEqual(self.client.get(reverse('App_Quanly:audit_log')).status_code, 403)

        self.login(self.manager)
        response = self.client.get(reverse('App_Quanly:audit_log'))
        self.assertContains(response, 'own tenant entry')
        self.assertNotContains(response, 'other tenant secret')
        filtered = self.client.get(reverse('App_Quanly:audit_log'), {'action': 'group:0'})
        self.assertNotContains(filtered, 'own tenant entry')

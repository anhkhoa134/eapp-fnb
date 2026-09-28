"""Test cho các bản sửa sau rà soát 28/09/2026: thuế theo cấu hình, chặn tính năng theo cờ/gói,
chống tạo đơn trùng, giới hạn đầu vào, gói hết hạn với đơn QR, xoá nhân viên có đơn, bếp."""

import json
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import User
from App_Catalog.models import ProductTopping, Topping
from App_Sales.models import (
    Customer,
    KitchenTicket,
    KitchenTicketItem,
    Order,
    Promotion,
    QROrder,
    TableCartItem,
)
from App_Sales.services import MAX_ITEM_QUANTITY, MAX_ORDER_LINES
from App_Sales.tests_ops import OpsTestBase
from App_Tenant.models import SubscriptionPlan
from App_Tenant.services import provision_tenant_default_setup


class TaxSettingTests(OpsTestBase):
    def test_checkout_uses_tenant_tax_and_ignores_client_tax_rate(self):
        self.tenant.tax_percent = Decimal('8')
        self.tenant.save()
        self.login(self.staff)
        response = self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'card',
                'tax_rate': '5',  # client cố tình gửi 500% -> bị bỏ qua
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(pk=response.json()['order_id'])
        self.assertEqual(order.tax_rate, Decimal('0.08'))
        self.assertEqual(order.tax_amount, Decimal('2400'))
        self.assertEqual(order.total_amount, Decimal('32400'))

    def test_tax_is_rounded_to_whole_dong_and_cash_must_cover_it(self):
        self.tenant.tax_percent = Decimal('8.5')
        self.tenant.save()
        self.login(self.staff)
        self.add_to_table(quantity=1)
        # 30.000 * 8.5% = 2.550 -> tổng 32.550; đưa 32.549 là thiếu.
        short = self.post_json(
            reverse('App_Sales_API:table_checkout', args=[self.table.id]),
            {'payment_method': 'cash', 'customer_paid': '32549'},
        )
        self.assertEqual(short.status_code, 400)
        ok = self.post_json(
            reverse('App_Sales_API:table_checkout', args=[self.table.id]),
            {'payment_method': 'cash', 'customer_paid': '32550'},
        )
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.json()['tax_amount'], 2550.0)

    def test_receipt_and_table_bill_show_tax(self):
        self.tenant.tax_percent = Decimal('10')
        self.tenant.save()
        self.login(self.staff)
        self.add_to_table(quantity=1)
        bill = self.client.get(reverse('App_Sales:table_bill', args=[self.table.id]))
        self.assertContains(bill, 'Thuế (10%)')
        self.assertContains(bill, '33.000')
        order = self.checkout_takeaway(payment_method='card', customer_paid='0')
        receipt = self.client.get(reverse('App_Sales:order_receipt', args=[order.id]))
        self.assertContains(receipt, 'Thuế (10%)')

    def test_manager_sets_tax_on_feature_settings_page(self):
        self.login(self.manager)
        url = reverse('App_Quanly:feature_settings')
        page = self.client.get(url)
        self.assertContains(page, 'Mức thuế (%)')

        response = self.client.post(url, {'form_action': 'tax', 'tax_percent': '8'})
        self.assertRedirects(response, url)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.tax_percent, Decimal('8'))
        # Lưu thuế không được đụng tới công tắc tính năng.
        self.assertTrue(self.tenant.show_kitchen_feature)

        too_high = self.client.post(url, {'form_action': 'tax', 'tax_percent': '80'})
        self.assertEqual(too_high.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.tax_percent, Decimal('8'))

    def test_staff_cannot_change_tax(self):
        self.login(self.staff)
        response = self.client.post(reverse('App_Quanly:feature_settings'), {'form_action': 'tax', 'tax_percent': '5'})
        self.assertEqual(response.status_code, 403)


class FeatureFlagEnforcementTests(OpsTestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(tenant=self.tenant, name='Khách A', phone='0901234567')
        self.promotion = Promotion.objects.create(
            tenant=self.tenant,
            name='Giảm 10%',
            discount_type=Promotion.DiscountType.PERCENT,
            discount_value=Decimal('10'),
            is_active=True,
        )

    def _checkout(self, **extra):
        return self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'card',
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
                **extra,
            },
        )

    def test_customer_feature_off_blocks_pages_and_apis(self):
        self.tenant.show_customer_feature = False
        self.tenant.save()
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse('App_Quanly:customers')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:customer_edit', args=[self.customer.id])).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse('App_Quanly:customer_delete', args=[self.customer.id])).status_code, 403
        )
        self.assertEqual(self.client.get(reverse('App_Sales_API:customers')).status_code, 403)
        response = self._checkout(customer_id=self.customer.id)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_promotion_feature_off_blocks_pages_and_apis(self):
        self.tenant.show_promotion_feature = False
        self.tenant.save()
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse('App_Quanly:promotions')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:promotion_edit', args=[self.promotion.id])).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse('App_Sales_API:promotions'), {'store_id': self.store.id}).status_code, 403
        )
        self.assertEqual(self._checkout(promotion_id=self.promotion.id).status_code, 400)

    def test_plan_without_feature_blocks_even_if_flag_is_on(self):
        plan = SubscriptionPlan.objects.create(name='Gói thử', feature_customer=False, feature_promotion=False)
        self.tenant.subscription_plan = plan
        self.tenant.show_customer_feature = True
        self.tenant.show_promotion_feature = True
        self.tenant.save()
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse('App_Quanly:customers')).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Quanly:promotions')).status_code, 403)
        self.assertEqual(self._checkout(customer_id=self.customer.id).status_code, 400)

    def test_features_on_still_work(self):
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse('App_Quanly:customers')).status_code, 200)
        response = self._checkout(customer_id=self.customer.id, promotion_id=self.promotion.id)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['discount_amount'], 3000.0)


class DuplicateCheckoutTests(OpsTestBase):
    def test_takeaway_retry_with_same_request_id_returns_same_order(self):
        self.login(self.staff)
        payload = {
            'store_id': self.store.id,
            'payment_method': 'cash',
            'customer_paid': '50000',
            'client_request_id': 'pay-0001-abcdef',
            'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
        }
        first = self.post_json(reverse('App_Sales_API:checkout'), payload)
        second = self.post_json(reverse('App_Sales_API:checkout'), payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['replayed'])
        self.assertEqual(first.json()['order_id'], second.json()['order_id'])
        self.assertEqual(Order.objects.count(), 1)

    def test_table_checkout_twice_creates_one_order(self):
        self.login(self.staff)
        self.add_to_table(quantity=2)
        url = reverse('App_Sales_API:table_checkout', args=[self.table.id])
        payload = {'payment_method': 'card', 'client_request_id': 'pay-table-0001'}
        first = self.post_json(url, payload)
        replay = self.post_json(url, payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()['order_id'], first.json()['order_id'])
        # Không có mã (client cũ): giỏ đã trống -> không tạo đơn thứ hai.
        without_key = self.post_json(url, {'payment_method': 'card'})
        self.assertEqual(without_key.status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_request_id_is_scoped_per_tenant(self):
        self.login(self.staff)
        self.checkout_takeaway()
        order = Order.objects.get()
        order.client_request_id = 'shared-key-123'
        order.save(update_fields=['client_request_id'])
        other = provision_tenant_default_setup(
            type(self.tenant).objects.create(name='Khác', public_slug='khac-tenant')
        )
        self.client.force_login(other['manager_user'])
        unit = other['store'].product_links.select_related('product').first().product.units.first()
        response = self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': other['store'].id,
                'payment_method': 'card',
                'client_request_id': 'shared-key-123',
                'items': [{'product_id': unit.product_id, 'unit_id': unit.id, 'quantity': 1}],
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.count(), 2)


class InputLimitTests(OpsTestBase):
    def _checkout(self, items, **extra):
        return self.post_json(
            reverse('App_Sales_API:checkout'),
            {'store_id': self.store.id, 'payment_method': 'card', 'items': items, **extra},
        )

    def test_quantity_and_lines_are_bounded(self):
        self.login(self.staff)
        line = {'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}
        self.assertEqual(self._checkout([dict(line, quantity=10**15)]).status_code, 400)
        self.assertEqual(self._checkout([dict(line, quantity=MAX_ITEM_QUANTITY + 1)]).status_code, 400)
        self.assertEqual(self._checkout([line] * (MAX_ORDER_LINES + 1)).status_code, 400)
        self.assertEqual(self._checkout(['not-an-object']).status_code, 400)
        self.assertEqual(self._checkout([line], customer_paid='1e20').status_code, 400)
        self.assertEqual(self._checkout([dict(line, quantity=MAX_ITEM_QUANTITY)]).status_code, 201)

    def test_non_object_json_body_is_rejected(self):
        self.login(self.staff)
        response = self.client.post(reverse('App_Sales_API:checkout'), data='[1, 2]', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_table_cart_quantity_is_bounded(self):
        self.login(self.staff)
        url = reverse('App_Sales_API:table_cart_add', args=[self.table.id])
        too_many = self.post_json(url, {'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 10**12})
        self.assertEqual(too_many.status_code, 400)
        self.add_to_table(quantity=1)
        item = TableCartItem.objects.get(table=self.table)
        patch = self.client.patch(
            reverse('App_Sales_API:table_cart_item', args=[self.table.id, item.id]),
            data=json.dumps({'quantity': 10**12}),
            content_type='application/json',
        )
        self.assertEqual(patch.status_code, 400)

    def test_public_qr_order_quantity_is_bounded(self):
        response = self.post_json(
            reverse('App_Public_API:qr_orders_create'),
            {
                'table_code': self.table.code,
                'token': self.table.qr_token,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 10**15}],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(QROrder.objects.exists())


class ExpiredSubscriptionQrTests(OpsTestBase):
    def setUp(self):
        super().setUp()
        self.tenant.subscription_ends_on = timezone.localdate() - timedelta(days=1)
        self.tenant.save()

    def test_dine_in_qr_order_rejected_when_subscription_expired(self):
        items = [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}]
        response = self.post_json(
            reverse('App_Public_API:qr_orders_create'),
            {'table_code': self.table.code, 'token': self.table.qr_token, 'items': items},
        )
        self.assertEqual(response.status_code, 403)
        page = self.client.get(
            reverse('App_Public:tenant_qr_ordering', args=[self.tenant.public_slug]),
            {'table_code': self.table.code, 'token': self.table.qr_token},
        )
        self.assertContains(page, 'Quán tạm ngưng gọi món qua mã QR')

    def test_pending_order_cannot_be_edited_but_can_be_cancelled_after_expiry(self):
        order = QROrder.objects.create(
            tenant=self.tenant, store=self.store, table=self.table, status=QROrder.Status.PENDING
        )
        creds = {'table_code': self.table.code, 'token': self.table.qr_token}
        patch = self.client.patch(
            reverse('App_Public_API:qr_orders_detail', args=[order.id]),
            data=json.dumps({**creds, 'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}]}),
            content_type='application/json',
        )
        self.assertEqual(patch.status_code, 403)
        cancel = self.post_json(reverse('App_Public_API:qr_orders_cancel', args=[order.id]), creds)
        self.assertEqual(cancel.status_code, 200)


class StaffDeleteTests(OpsTestBase):
    def test_delete_staff_with_orders_shows_message_instead_of_500(self):
        self.login(self.staff)
        self.checkout_takeaway()
        self.login(self.manager)
        response = self.client.post(reverse('App_Quanly:staff_delete', args=[self.staff.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'đã có đơn bán')
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())

    def test_delete_staff_without_orders_still_works(self):
        self.login(self.manager)
        response = self.client.post(reverse('App_Quanly:staff_delete', args=[self.staff.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.staff.pk).exists())


class KitchenConsistencyTests(OpsTestBase):
    def setUp(self):
        super().setUp()
        self.topping = Topping.objects.create(tenant=self.tenant, name='Trân châu', price=Decimal('5000'))
        ProductTopping.objects.create(product=self.product, topping=self.topping, price=Decimal('5000'))

    def test_takeaway_online_order_sends_only_extra_items_at_payment(self):
        created = self.post_json(
            reverse('App_Public_API:takeaway_orders_create'),
            {
                'tenant_slug': self.tenant.public_slug,
                'store_id': self.store.id,
                'customer_name': 'An',
                'customer_phone': '0901234567',
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
            },
        )
        self.assertEqual(created.status_code, 201, created.content)
        qr_order_id = created.json()['qr_order_id']
        self.login(self.staff)
        self.post_json(reverse('App_Sales_API:qr_order_approve', args=[qr_order_id]), {})
        self.assertEqual(KitchenTicket.objects.count(), 1)

        # Khách tới lấy, gọi thêm 2 ly: thu ngân thu tiền 3 ly.
        response = self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'card',
                'qr_order_id': qr_order_id,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 3}],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(KitchenTicket.objects.count(), 2)
        extra_ticket = KitchenTicket.objects.get(pk=response.json()['kitchen_ticket_id'])
        self.assertEqual([item.quantity for item in extra_ticket.items.all()], [2])

    def test_takeaway_online_order_without_extras_creates_no_new_ticket(self):
        created = self.post_json(
            reverse('App_Public_API:takeaway_orders_create'),
            {
                'tenant_slug': self.tenant.public_slug,
                'store_id': self.store.id,
                'customer_name': 'An',
                'customer_phone': '0901234567',
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2}],
            },
        )
        qr_order_id = created.json()['qr_order_id']
        self.login(self.staff)
        self.post_json(reverse('App_Sales_API:qr_order_approve', args=[qr_order_id]), {})
        response = self.post_json(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'card',
                'qr_order_id': qr_order_id,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2}],
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['kitchen_ticket_id'])
        self.assertEqual(KitchenTicket.objects.count(), 1)

    def test_invalid_topping_patch_does_not_cancel_sent_kitchen_items(self):
        self.login(self.staff)
        self.add_to_table(quantity=2)
        self.post_json(reverse('App_Sales_API:table_kitchen_send', args=[self.table.id]), {})
        item = TableCartItem.objects.get(table=self.table)
        response = self.client.patch(
            reverse('App_Sales_API:table_cart_item', args=[self.table.id, item.id]),
            data=json.dumps({'quantity': 1, 'topping_ids': [999999]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual((item.quantity, item.kitchen_sent_quantity), (2, 2))
        self.assertFalse(KitchenTicketItem.objects.filter(status=KitchenTicketItem.Status.CANCELLED).exists())


class HardeningMiscTests(OpsTestBase):
    def test_bootstrapped_manager_cannot_enter_django_admin(self):
        tenant = type(self.tenant).objects.create(name='Mới', public_slug='moi-tenant')
        result = provision_tenant_default_setup(tenant)
        self.assertFalse(result['manager_user'].is_staff)

    def test_public_menu_escapes_quotes_in_attributes(self):
        page = self.client.get(reverse('App_Public:tenant_catalog', args=[self.tenant.public_slug]))
        self.assertContains(page, ".replace(/\"/g, '&quot;')")

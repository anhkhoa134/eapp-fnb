import json
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse

from App_Catalog.models import ProductTopping, StoreProduct, Topping
from App_Core.models import AuditLog
from App_Sales.models import DiningTable, Order, TableCartItem
from App_Sales.tests_ops import OpsTestBase
from App_Tenant.models import Tenant


class PriceOverrideTests(OpsTestBase):
    def setUp(self):
        super().setUp()
        self.tenant.feature_price_override_enabled = True
        self.tenant.save(update_fields=['feature_price_override_enabled'])
        self.login(self.staff)

    def payload(self, **kwargs):
        return {'store_id': self.store.pk, 'product_id': self.product.pk, 'unit_id': self.unit.pk,
                'override_price': '25000', 'price_override_reason': 'Khách quen', **kwargs}

    def price(self, **kwargs):
        return self.post_json(reverse('App_Sales_API:cart_price'), self.payload(**kwargs))

    def checkout(self, token, **kwargs):
        return self.post_json(reverse('App_Sales_API:checkout'), {
            'store_id': self.store.pk, 'payment_method': 'cash', 'customer_paid': '100000',
            'items': [{'product_id': self.product.pk, 'unit_id': self.unit.pk, 'quantity': 2,
                       'price_override_token': token}], **kwargs,
        })

    def patch(self, item, **kwargs):
        return self.client.patch(reverse('App_Sales_API:table_cart_item', args=[item.table_id, item.pk]),
                                 data=json.dumps(kwargs), content_type='application/json')

    def logs(self):
        return AuditLog.objects.filter(action=AuditLog.Action.CART_PRICE_OVERRIDE)

    def disable(self):
        self.tenant.feature_price_override_enabled = False
        self.tenant.save(update_fields=['feature_price_override_enabled'])

    def test_default_off_and_manager_only_configuration(self):
        self.assertFalse(Tenant(name='new').feature_price_override_enabled)
        url = reverse('App_Quanly:feature_settings')
        self.assertEqual(self.client.post(url, {'feature_price_override_enabled': 'on'}).status_code, 403)
        self.login(self.manager)
        response = self.client.post(url, {'show_store_feature': 'on', 'feature_price_override_enabled': 'on', 'price_override_reason_required': 'on'})
        self.assertEqual(response.status_code, 302)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.feature_price_override_enabled)
        self.assertTrue(self.tenant.price_override_reason_required)

    def test_takeaway_immediate_audit_and_original_editor_at_checkout(self):
        response = self.price()
        self.assertEqual(response.status_code, 200, response.content)
        log = self.logs().get()
        self.assertEqual((log.user_id, log.tenant_id, log.store_id), (self.staff.pk, self.tenant.pk, self.store.pk))
        self.assertEqual(log.extra['before'], '30000.00')
        self.assertEqual(Decimal(log.extra['after']), Decimal('25000'))
        self.login(self.manager)
        response = self.checkout(response.json()['price_override_token'], client_request_id='price-test-replay-0001')
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(pk=response.json()['order_id'])
        item = order.items.get()
        self.assertEqual(order.subtotal, Decimal('50000'))
        self.assertEqual(item.unit_price, Decimal('25000'))
        self.assertEqual(item.original_unit_price, Decimal('30000'))
        self.assertEqual(item.price_overridden_by_id, self.staff.pk)
        self.assertEqual(item.price_overridden_by_name, self.staff.username)
        self.assertEqual(item.price_override_reason, 'Khách quen')
        self.assertEqual(order.cashier_id, self.manager.pk)
        self.assertEqual(self.logs().count(), 1)
        # Retry a successful payment must not duplicate the order or price audit.
        replay = self.checkout(None, client_request_id='price-test-replay-0001')
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.logs().count(), 1)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.price, Decimal('30000'))

    def test_invalid_prices_and_required_reason_do_not_write_audit(self):
        for value in ('', '-1', 'NaN', 'Infinity', '1.234', '1000000000000', True, {}, []):
            with self.subTest(value=value):
                response = self.price(override_price=value)
                self.assertEqual(response.status_code, 400, response.content)
        self.tenant.price_override_reason_required = True
        self.tenant.save(update_fields=['price_override_reason_required'])
        for reason in (' ', 'a' * 256, {}, None):
            self.assertEqual(self.price(price_override_reason=reason).status_code, 400)
        self.assertEqual(self.logs().count(), 0)

    def test_zero_decimal_and_store_specific_original_price(self):
        StoreProduct.objects.filter(store=self.store, product=self.product).update(custom_price=Decimal('32000'))
        response = self.price(override_price='0')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['price'], 0)
        self.assertEqual(response.json()['original_price'], 32000)
        response = self.price(override_price='12500.50')
        payment = self.checkout(response.json()['price_override_token'])
        self.assertEqual(payment.status_code, 201, payment.content)
        self.assertEqual(Order.objects.get().subtotal, Decimal('25001'))

    def test_disabled_blocks_edit_and_checkout_but_allows_restore(self):
        token = self.price().json()['price_override_token']
        self.disable()
        self.assertEqual(self.price().status_code, 403)
        self.assertEqual(self.checkout(token).status_code, 403)
        restored = self.price(override_price=None, price_override_token=token)
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertIsNone(restored.json()['price_override_token'])
        self.assertEqual(restored.json()['price'], 30000)
        self.assertTrue(self.logs().first().extra['restored'])
        self.assertEqual(self.checkout(None).status_code, 201)

    def test_signed_price_cannot_be_forged_or_reused_for_other_store_or_toppings(self):
        token = self.price().json()['price_override_token']
        self.assertEqual(self.checkout(token + 'x').status_code, 400)
        self.assertEqual(self.price(store_id=self.other_store.pk).status_code, 403)
        self.login(self.manager)
        StoreProduct.objects.create(store=self.other_store, product=self.product, is_available=True)
        response = self.checkout(token, store_id=self.other_store.pk)
        self.assertEqual(response.status_code, 400, response.content)
        topping = Topping.objects.create(tenant=self.tenant, name='Thêm sữa', price=5000)
        ProductTopping.objects.create(product=self.product, topping=topping, price=5000)
        response = self.checkout(token, items=[{
            'product_id': self.product.pk, 'unit_id': self.unit.pk, 'quantity': 1,
            'topping_ids': [topping.pk], 'price_override_token': token,
        }])
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Order.objects.count(), 0)

    def test_raw_unverified_checkout_price_is_rejected(self):
        response = self.checkout(None, items=[{
            'product_id': self.product.pk, 'unit_id': self.unit.pk, 'quantity': 1,
            'override_price': 1, 'price_overridden_by_id': self.manager.pk,
        }])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.logs().count(), 0)

    def test_table_edit_quantity_add_and_move_preserve_price_and_actor(self):
        self.add_to_table(quantity=2)
        item = TableCartItem.objects.get(table=self.table)
        response = self.patch(item, override_price='20000', price_override_reason='Giảm riêng')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.patch(item, quantity=3, note='Ít đá').status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.unit_price_snapshot, Decimal('20000'))
        self.assertEqual(item.price_overridden_by_id, self.staff.pk)
        self.add_to_table(quantity=1)
        self.assertEqual(TableCartItem.objects.filter(table=self.table).count(), 2)
        self.login(self.manager)
        other = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='B02', name='Bàn 02')
        result = self.post_json(reverse('App_Sales_API:table_cart_move_to', args=[self.table.pk]), {
            'to_table_id': other.pk, 'item_ids': [item.pk],
        })
        self.assertEqual(result.status_code, 200, result.content)
        moved = TableCartItem.objects.get(table=other)
        self.assertEqual(moved.unit_price_snapshot, Decimal('20000'))
        self.assertEqual(moved.price_overridden_by_id, self.staff.pk)
        result = self.post_json(reverse('App_Sales_API:table_checkout', args=[other.pk]), {
            'payment_method': 'cash', 'customer_paid': '100000', 'item_ids': [moved.pk],
        })
        self.assertEqual(result.status_code, 201, result.content)
        order = Order.objects.get(pk=result.json()['order_id'])
        self.assertEqual(order.subtotal, Decimal('60000'))
        self.assertEqual(order.items.get().price_overridden_by_id, self.staff.pk)
        self.assertEqual(self.logs().count(), 1)

    def test_table_disable_restore_and_foreign_table_permissions(self):
        self.add_to_table(quantity=1)
        item = TableCartItem.objects.get(table=self.table)
        self.assertEqual(self.patch(item, override_price='10000').status_code, 200)
        self.disable()
        self.assertEqual(self.patch(item, override_price='1').status_code, 403)
        response = self.post_json(reverse('App_Sales_API:table_checkout', args=[self.table.pk]), {
            'payment_method': 'cash', 'customer_paid': '100000',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.patch(item, override_price=None).status_code, 200)
        item.refresh_from_db()
        self.assertIsNone(item.original_unit_price)
        self.assertIsNone(item.price_overridden_by_id)
        self.assertEqual(item.unit_price_snapshot, Decimal('30000'))
        table = DiningTable.objects.create(tenant=self.tenant, store=self.other_store, code='X', name='X')
        response = self.client.patch(reverse('App_Sales_API:table_cart_item', args=[table.pk, item.pk]),
                                     data='{"override_price":"1"}', content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_import_table_and_back_to_takeaway_keep_original_editor(self):
        token = self.price().json()['price_override_token']
        self.login(self.manager)
        response = self.post_json(reverse('App_Sales_API:table_import_takeaway', args=[self.table.pk]), {
            'items': [{'product_id': self.product.pk, 'unit_id': self.unit.pk, 'quantity': 1, 'price_override_token': token}],
        })
        self.assertEqual(response.status_code, 201, response.content)
        item = TableCartItem.objects.get(table=self.table)
        self.assertEqual(item.price_overridden_by_id, self.staff.pk)
        response = self.client.get(reverse('App_Sales_API:table_cart', args=[self.table.pk]))
        transferred = response.json()['items'][0]['price_override_token']
        self.client.delete(reverse('App_Sales_API:table_cart_item', args=[self.table.pk, item.pk]))
        result = self.checkout(transferred)
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(Order.objects.get().items.get().price_overridden_by_id, self.staff.pk)

    def test_toppings_are_included_in_override_and_do_not_reset_it(self):
        topping = Topping.objects.create(tenant=self.tenant, name='Sữa', price=5000)
        ProductTopping.objects.create(product=self.product, topping=topping, price=5000)
        priced = self.price(topping_ids=[topping.pk], override_price='32000')
        self.assertEqual(priced.status_code, 200, priced.content)
        self.assertEqual(priced.json()['original_price'], 35000)
        self.add_to_table(quantity=1)
        item = TableCartItem.objects.get(table=self.table)
        self.assertEqual(self.patch(item, override_price='20000').status_code, 200)
        self.assertEqual(self.patch(item, topping_ids=[topping.pk]).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.unit_price_snapshot, Decimal('20000'))
        self.assertEqual(item.original_unit_price, Decimal('35000'))
        self.assertEqual(self.patch(item, override_price=None).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.unit_price_snapshot, Decimal('35000'))

    def test_invalid_import_rolls_back_and_excessive_total_cannot_checkout(self):
        token = self.price().json()['price_override_token']
        rows = [{'product_id': self.product.pk, 'unit_id': self.unit.pk, 'quantity': 1, 'price_override_token': token}]
        rows.append({**rows[0], 'price_override_token': 'tampered'})
        response = self.post_json(reverse('App_Sales_API:table_import_takeaway', args=[self.table.pk]), {'items': rows})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TableCartItem.objects.filter(table=self.table).exists())
        token = self.price(override_price='999999999999').json()['price_override_token']
        self.assertEqual(self.checkout(token).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_manager_can_filter_price_audit_and_see_order_editor(self):
        token = self.price().json()['price_override_token']
        self.checkout(token)
        self.login(self.manager)
        response = self.client.get(reverse('App_Quanly:audit_log'), {'action': 'cart.price_override'})
        self.assertContains(response, self.staff.username)
        self.assertContains(response, 'Khách quen')
        self.assertContains(response, 'Chỉnh giá bán')
        history = self.client.get(reverse('App_Quanly:orders'))
        self.assertContains(history, f'Chỉnh bởi {self.staff.username}')

    def test_failed_audit_rolls_back_table_price(self):
        self.add_to_table(quantity=1)
        item = TableCartItem.objects.get(table=self.table)
        with patch('App_Sales.pricing.log_action', return_value=None), self.assertRaises(RuntimeError):
            self.patch(item, override_price='10000')
        item.refresh_from_db()
        self.assertEqual(item.unit_price_snapshot, Decimal('30000'))
        self.assertIsNone(item.original_unit_price)

    def test_table_partial_checkout_preserves_unpaid_lines(self):
        self.add_to_table(quantity=1)
        adjusted = TableCartItem.objects.get(table=self.table)
        self.patch(adjusted, override_price='20000')
        self.add_to_table(quantity=2)
        response = self.post_json(reverse('App_Sales_API:table_checkout', args=[self.table.pk]), {
            'payment_method': 'cash', 'customer_paid': '100000', 'item_ids': [adjusted.pk],
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['partial'])
        self.assertEqual(Order.objects.get().items.get().unit_price, Decimal('20000'))
        unpaid = TableCartItem.objects.get(table=self.table)
        self.assertEqual(unpaid.unit_price_snapshot * unpaid.quantity, Decimal('60000'))

    def test_override_totals_include_discounts_tax_and_receipt(self):
        from App_Sales.models import Promotion
        self.tenant.tax_percent = Decimal('10')
        self.tenant.save(update_fields=['tax_percent'])
        promotion = Promotion.objects.create(
            tenant=self.tenant, name='Giảm 10%', discount_type=Promotion.DiscountType.PERCENT,
            discount_value=Decimal('10'),
        )
        token = self.price().json()['price_override_token']
        response = self.checkout(token, promotion_id=promotion.pk)
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get()
        self.assertEqual(order.subtotal, Decimal('50000'))
        self.assertEqual(order.discount_amount, Decimal('5000'))
        self.assertEqual(order.tax_amount, Decimal('4500'))
        self.assertEqual(order.total_amount, Decimal('49500'))
        receipt = self.client.get(reverse('App_Sales:order_receipt', args=[order.pk]))
        self.assertContains(receipt, '25.000')
        self.assertContains(receipt, '49.500')

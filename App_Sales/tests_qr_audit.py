"""Regression coverage for the QR/POS PostgreSQL audit (2026-09-30)."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, connections, transaction
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from App_Sales import realtime
from App_Sales.models import DiningTable, KitchenTicket, Order, QROrder, QROrderItem, TableCartItem
from App_Sales.tests_ops import OpsTestBase


class RealtimeFailureTests(SimpleTestCase):
    def test_channel_initialization_failure_does_not_escape_notification(self):
        with patch.object(realtime, '_channel_layer_retry_after', 0), patch.object(
            realtime, 'get_channel_layer', side_effect=ImproperlyConfigured('Unavailable backend')
        ), self.assertLogs('App_Sales.realtime', level='WARNING'):
            realtime.notify_qr_order_changed(store_id=1, order_id=1, status='PENDING', reason='created')


class QrAuditApiTests(OpsTestBase):
    def test_non_finite_payment_is_rejected_without_creating_order(self):
        self.login(self.staff)
        for amount in ['NaN', 'sNaN', 'Infinity', '-Infinity']:
            with self.subTest(amount=amount):
                response = self.post_json(reverse('App_Sales_API:checkout'), {
                    'store_id': self.store.id, 'payment_method': 'cash', 'customer_paid': amount,
                    'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
                })
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_qr_creation_succeeds_when_channel_backend_cannot_initialize(self):
        with patch.object(realtime, '_channel_layer_retry_after', 0), patch.object(
            realtime, 'get_channel_layer', side_effect=ImproperlyConfigured('Unavailable backend')
        ), self.assertLogs('App_Sales.realtime', level='WARNING'):
            response = self.post_json(reverse('App_Public_API:qr_orders_create'), {
                'table_code': self.table.code, 'token': self.table.qr_token,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(QROrder.objects.count(), 1)

    def test_checkout_replay_cannot_return_another_stores_order(self):
        self.login(self.manager)
        order = self.checkout_takeaway()
        order.client_request_id = 'audit-existing-order'
        order.save(update_fields=['client_request_id'])
        self.login(self.staff)
        # The staff can access self.store but not the order's other_store.
        Order.objects.filter(pk=order.pk).update(store=self.other_store)
        response = self.post_json(reverse('App_Sales_API:checkout'), {
            'store_id': self.store.id, 'client_request_id': order.client_request_id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('order_id', response.json())


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
@skipUnlessDBFeature('has_select_for_update')
class CartConcurrencyTests(TransactionTestCase):
    setUp = OpsTestBase.setUp
    post_json = OpsTestBase.post_json
    add_to_table = OpsTestBase.add_to_table

    def test_edit_waits_for_checkout_and_cannot_restore_paid_items(self):
        self.client.force_login(self.staff)
        self.add_to_table(quantity=2)
        item = TableCartItem.objects.get(table=self.table)
        started = Event()
        finished = Event()

        def edit_from_other_terminal():
            try:
                client = Client()
                client.force_login(self.staff)

                def mark_table_query(execute, sql, params, many, context):
                    if 'App_Sales_diningtable' in sql:
                        started.set()
                    return execute(sql, params, many, context)

                with connection.execute_wrapper(mark_table_query):
                    return client.patch(
                        reverse('App_Sales_API:table_cart_item', args=[self.table.id, item.id]),
                        data=json.dumps({'quantity': 3}), content_type='application/json',
                    ).status_code
            finally:
                finished.set()
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                DiningTable.objects.select_for_update().get(pk=self.table.pk)
                pending = pool.submit(edit_from_other_terminal)
                self.assertTrue(started.wait(5))
                edited_before_checkout = finished.wait(0.3)
                response = self.post_json(reverse('App_Sales_API:table_checkout', args=[self.table.id]), {
                    'payment_method': 'cash', 'customer_paid': 100000,
                })
            status = pending.result(timeout=5)
        self.assertFalse(edited_before_checkout)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(status, 404)
        self.assertEqual(Order.objects.get().items.get().quantity, 2)
        self.assertFalse(TableCartItem.objects.filter(table=self.table).exists())

    def test_two_terminals_approve_once(self):
        order = QROrder.objects.create(tenant=self.tenant, store=self.store, table=self.table)
        QROrderItem.objects.create(
            qr_order=order, product=self.product, unit=self.unit,
            snapshot_product_name=self.product.name, snapshot_unit_name=self.unit.name,
            unit_price_snapshot=self.unit.price, quantity=2,
        )
        ready = Barrier(2)

        def approve():
            try:
                client = Client()
                client.force_login(self.staff)
                ready.wait(timeout=5)
                return client.post(reverse('App_Sales_API:qr_order_approve', args=[order.id])).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(approve)
            second = pool.submit(approve)
            self.assertEqual([first.result(timeout=10), second.result(timeout=10)], [200, 200])
        order.refresh_from_db()
        self.assertEqual(order.status, QROrder.Status.APPROVED)
        self.assertEqual(TableCartItem.objects.get(table=self.table).quantity, 2)
        self.assertEqual(KitchenTicket.objects.filter(qr_order=order).count(), 1)

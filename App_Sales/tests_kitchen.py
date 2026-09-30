import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Sales.models import (
    DiningTable,
    KitchenTicket,
    KitchenTicketItem,
    Order,
    QROrder,
    QROrderItem,
    TableCartItem,
)
from App_Tenant.models import Store, Tenant, UserStoreAccess


class KitchenFeatureTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo', show_kitchen_feature=True)
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.staff = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

        category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        StoreCategory.objects.create(store=self.store, category=category, is_visible=True)
        self.product = Product.objects.create(tenant=self.tenant, category=category, name='Cà phê sữa')
        self.unit = ProductUnit.objects.create(product=self.product, name='Ly', price=Decimal('20000'))
        StoreProduct.objects.create(store=self.store, product=self.product, is_available=True)
        self.topping = Topping.objects.create(tenant=self.tenant, name='Thêm shot', is_active=True)
        ProductTopping.objects.create(product=self.product, topping=self.topping, price=Decimal('5000'), is_active=True)

        self.table_1 = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='B1', name='Bàn 1')
        self.table_2 = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='B2', name='Bàn 2')

        self.client.login(username='staff_demo', password='123456')

    # helpers
    def _post(self, url, payload=None):
        return self.client.post(url, data=json.dumps(payload or {}), content_type='application/json')

    def _add_to_table(self, table, quantity=1, **extra):
        url = reverse('App_Sales_API:table_cart_add', kwargs={'table_id': table.id})
        res = self._post(url, {'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': quantity, **extra})
        self.assertEqual(res.status_code, 201)
        return TableCartItem.objects.get(id=res.json()['item']['id'])

    def _send(self, table):
        return self._post(reverse('App_Sales_API:table_kitchen_send', kwargs={'table_id': table.id}))

    def _patch_item(self, table, item, payload):
        url = reverse('App_Sales_API:table_cart_item', kwargs={'table_id': table.id, 'item_id': item.id})
        return self.client.patch(url, data=json.dumps(payload), content_type='application/json')

    def _set_status(self, kitchen_item, status):
        url = reverse('App_Sales_API:kitchen_item_status', kwargs={'item_id': kitchen_item.id})
        return self._post(url, {'status': status})

    # page + feature flag
    def test_kitchen_page_requires_feature(self):
        self.assertEqual(self.client.get(reverse('App_Sales:kitchen')).status_code, 200)
        self.tenant.show_kitchen_feature = False
        self.tenant.save(update_fields=['show_kitchen_feature', 'updated_at'])
        self.assertEqual(self.client.get(reverse('App_Sales:kitchen')).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Sales_API:kitchen_tickets')).status_code, 403)
        self.assertEqual(self._send(self.table_1).status_code, 403)

    def test_pos_shows_kitchen_controls_only_when_enabled(self):
        html = self.client.get(reverse('App_Sales:pos')).content.decode('utf-8')
        self.assertIn('id="btn-kitchen-send"', html)
        self.assertIn(reverse('App_Sales:kitchen'), html)
        self.tenant.show_kitchen_feature = False
        self.tenant.save(update_fields=['show_kitchen_feature', 'updated_at'])
        html = self.client.get(reverse('App_Sales:pos')).content.decode('utf-8')
        self.assertNotIn('id="btn-kitchen-send"', html)

    # báo bếp giỏ bàn
    def test_send_table_cart_only_sends_unsent_quantity(self):
        self._add_to_table(self.table_1, quantity=2, note='Ít đá')
        res = self._send(self.table_1)
        self.assertEqual(res.status_code, 201)
        ticket = KitchenTicket.objects.get(id=res.json()['ticket_id'])
        self.assertEqual(ticket.source, KitchenTicket.Source.TABLE)
        self.assertEqual(ticket.table_name, 'Bàn 1')
        row = ticket.items.get()
        self.assertEqual((row.quantity, row.note, row.status), (2, 'Ít đá', KitchenTicketItem.Status.PENDING))

        item = self._add_to_table(self.table_1, quantity=1, note='Ít đá')
        self.assertEqual((item.quantity, item.kitchen_sent_quantity), (3, 2))
        res = self._send(self.table_1)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(KitchenTicket.objects.get(id=res.json()['ticket_id']).items.get().quantity, 1)

        res = self._send(self.table_1)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()['ticket_id'])
        self.assertEqual(KitchenTicket.objects.count(), 2)

    def test_send_includes_topping_text(self):
        self._add_to_table(self.table_1, topping_ids=[self.topping.id])
        self._send(self.table_1)
        self.assertEqual(KitchenTicketItem.objects.get().toppings_text, 'Thêm shot')

    def test_decrease_quantity_cancels_pending_kitchen_portion(self):
        item = self._add_to_table(self.table_1, quantity=3)
        self._send(self.table_1)

        res = self._patch_item(self.table_1, item, {'quantity': 1})
        self.assertEqual(res.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.kitchen_sent_quantity, 1)
        rows = {row.status: row.quantity for row in KitchenTicketItem.objects.all()}
        self.assertEqual(rows, {KitchenTicketItem.Status.PENDING: 1, KitchenTicketItem.Status.CANCELLED: 2})

    def test_delete_item_keeps_done_portion(self):
        item = self._add_to_table(self.table_1, quantity=1)
        self._send(self.table_1)
        self._set_status(KitchenTicketItem.objects.get(), KitchenTicketItem.Status.DONE)
        self._add_to_table(self.table_1, quantity=1)
        self._send(self.table_1)

        url = reverse('App_Sales_API:table_cart_item', kwargs={'table_id': self.table_1.id, 'item_id': item.id})
        self.assertEqual(self.client.delete(url).status_code, 200)
        statuses = sorted(KitchenTicketItem.objects.values_list('status', flat=True))
        self.assertEqual(statuses, [KitchenTicketItem.Status.CANCELLED, KitchenTicketItem.Status.DONE])
        self.assertFalse(KitchenTicket.objects.filter(completed_at__isnull=True).exists())

    def test_changing_note_of_sent_item_requires_resend(self):
        item = self._add_to_table(self.table_1, quantity=2)
        self._send(self.table_1)
        self._patch_item(self.table_1, item, {'note': 'Không đường'})
        item.refresh_from_db()
        self.assertEqual(item.kitchen_sent_quantity, 0)
        self.assertEqual(KitchenTicketItem.objects.get().status, KitchenTicketItem.Status.CANCELLED)

        res = self._send(self.table_1)
        self.assertEqual(KitchenTicket.objects.get(id=res.json()['ticket_id']).items.get().note, 'Không đường')

    def test_move_table_carries_sent_quantity_and_open_tickets(self):
        self._add_to_table(self.table_1, quantity=2)
        self._send(self.table_1)
        url = reverse('App_Sales_API:table_cart_move_to', kwargs={'table_id': self.table_1.id})
        self.assertEqual(self._post(url, {'to_table_id': self.table_2.id}).status_code, 200)

        moved = TableCartItem.objects.get(table=self.table_2)
        self.assertEqual(moved.kitchen_sent_quantity, 2)
        ticket = KitchenTicket.objects.get()
        self.assertEqual((ticket.table_id, ticket.table_name), (self.table_2.id, 'Bàn 2'))
        self.assertEqual(KitchenTicketItem.objects.get().table_cart_item_id, moved.id)

    def test_table_checkout_auto_sends_unsent_items(self):
        self._add_to_table(self.table_1, quantity=2)
        self._send(self.table_1)
        self._add_to_table(self.table_1, quantity=1)
        url = reverse('App_Sales_API:table_checkout', kwargs={'table_id': self.table_1.id})
        res = self._post(url, {'payment_method': 'cash', 'tax_rate': 0, 'customer_paid': 100000})
        self.assertEqual(res.status_code, 201)

        self.assertEqual(KitchenTicket.objects.count(), 2)
        last = KitchenTicket.objects.order_by('-id').first()
        self.assertEqual(last.order_id, res.json()['order_id'])
        self.assertEqual(last.items.get().quantity, 1)
        self.assertEqual(KitchenTicketItem.objects.filter(table_cart_item__isnull=False).count(), 0)

    def test_takeaway_checkout_creates_ticket(self):
        res = self._post(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'cash',
                'tax_rate': 0,
                'customer_paid': 100000,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2, 'note': 'Mang đi'}],
            },
        )
        self.assertEqual(res.status_code, 201)
        ticket = KitchenTicket.objects.get()
        order = Order.objects.get()
        self.assertEqual(ticket.source, KitchenTicket.Source.TAKEAWAY)
        self.assertEqual(ticket.order_id, order.id)
        self.assertIn(order.order_code, ticket.table_name)
        self.assertEqual(ticket.items.get().quantity, 2)

    def test_takeaway_checkout_without_feature_creates_no_ticket(self):
        self.tenant.show_kitchen_feature = False
        self.tenant.save(update_fields=['show_kitchen_feature', 'updated_at'])
        res = self._post(
            reverse('App_Sales_API:checkout'),
            {
                'store_id': self.store.id,
                'payment_method': 'cash',
                'tax_rate': 0,
                'customer_paid': 100000,
                'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
            },
        )
        self.assertEqual(res.status_code, 201)
        self.assertFalse(KitchenTicket.objects.exists())

    def test_qr_approve_creates_ticket_and_marks_items_sent(self):
        qr_order = QROrder.objects.create(tenant=self.tenant, store=self.store, table=self.table_1)
        QROrderItem.objects.create(
            qr_order=qr_order,
            product=self.product,
            unit=self.unit,
            snapshot_product_name=self.product.name,
            snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('20000'),
            quantity=2,
            line_total=Decimal('0'),
        )
        res = self._post(reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id}))
        self.assertEqual(res.status_code, 200)

        ticket = KitchenTicket.objects.get()
        self.assertEqual((ticket.source, ticket.qr_order_id), (KitchenTicket.Source.QR, qr_order.id))
        cart_item = TableCartItem.objects.get(table=self.table_1)
        self.assertEqual(cart_item.kitchen_sent_quantity, 2)
        self.assertEqual(ticket.items.get().table_cart_item_id, cart_item.id)
        self.assertIsNone(self._send(self.table_1).json()['ticket_id'])

        # Retrying approval must not add the items or send them to the kitchen twice.
        res = self._post(reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': qr_order.id}))
        self.assertEqual(res.status_code, 200)
        qr_order.refresh_from_db()
        cart_item.refresh_from_db()
        self.assertEqual(qr_order.status, QROrder.Status.APPROVED)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(KitchenTicket.objects.filter(qr_order=qr_order).count(), 1)

    # màn hình bếp
    def test_status_flow_completes_ticket_and_reports_to_pos(self):
        self._add_to_table(self.table_1, quantity=2)
        self._send(self.table_1)
        kitchen_item = KitchenTicketItem.objects.get()

        res = self._set_status(kitchen_item, KitchenTicketItem.Status.PREPARING)
        self.assertEqual(res.status_code, 200)
        kitchen_item.refresh_from_db()
        self.assertIsNotNone(kitchen_item.started_at)

        res = self._set_status(kitchen_item, KitchenTicketItem.Status.DONE)
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.json()['ticket']['completed_at'])

        cart = self.client.get(reverse('App_Sales_API:table_cart', kwargs={'table_id': self.table_1.id})).json()
        self.assertEqual(cart['items'][0]['kitchen_sent_qty'], 2)
        self.assertEqual(cart['items'][0]['kitchen_done_qty'], 2)

        # Hoàn tác mở lại phiếu.
        self._set_status(kitchen_item, KitchenTicketItem.Status.PREPARING)
        self.assertIsNone(KitchenTicket.objects.get().completed_at)

    def test_invalid_status_and_cancelled_item_rejected(self):
        self._add_to_table(self.table_1, quantity=1)
        self._send(self.table_1)
        kitchen_item = KitchenTicketItem.objects.get()
        self.assertEqual(self._set_status(kitchen_item, 'CANCELLED').status_code, 400)
        kitchen_item.status = KitchenTicketItem.Status.CANCELLED
        kitchen_item.save()
        self.assertEqual(self._set_status(kitchen_item, KitchenTicketItem.Status.DONE).status_code, 400)

    def test_complete_ticket_and_list_scopes(self):
        self._add_to_table(self.table_1, quantity=1)
        self._add_to_table(self.table_1, quantity=1, note='Nóng')
        self._send(self.table_1)
        self._add_to_table(self.table_2, quantity=1)
        self._send(self.table_2)

        tickets_url = reverse('App_Sales_API:kitchen_tickets')
        active = self.client.get(tickets_url, {'store_id': self.store.id}).json()
        self.assertEqual(active['active_count'], 2)
        self.assertEqual([t['table_name'] for t in active['tickets']], ['Bàn 1', 'Bàn 2'])

        first_id = active['tickets'][0]['id']
        res = self._post(reverse('App_Sales_API:kitchen_ticket_complete', kwargs={'ticket_id': first_id}))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(row['status'] == 'DONE' for row in res.json()['ticket']['items']))

        active = self.client.get(tickets_url, {'store_id': self.store.id}).json()
        self.assertEqual([t['table_name'] for t in active['tickets']], ['Bàn 2'])
        done = self.client.get(tickets_url, {'store_id': self.store.id, 'scope': 'done'}).json()
        self.assertEqual([t['id'] for t in done['tickets']], [first_id])

    def test_other_tenant_cannot_touch_kitchen_items(self):
        self._add_to_table(self.table_1, quantity=1)
        self._send(self.table_1)
        kitchen_item = KitchenTicketItem.objects.get()

        other = Tenant.objects.create(name='Other', public_slug='other', show_kitchen_feature=True)
        other_store = Store.objects.create(tenant=other, name='Other store', is_default=True)
        other_user = User.objects.create_user(username='other', password='123456', tenant=other, role=User.Role.STAFF)
        UserStoreAccess.objects.create(user=other_user, store=other_store, is_default=True)
        self.client.login(username='other', password='123456')

        self.assertEqual(self._set_status(kitchen_item, KitchenTicketItem.Status.DONE).status_code, 404)
        url = reverse('App_Sales_API:kitchen_ticket_complete', kwargs={'ticket_id': kitchen_item.ticket_id})
        self.assertEqual(self._post(url).status_code, 404)
        kitchen_item.refresh_from_db()
        self.assertEqual(kitchen_item.status, KitchenTicketItem.Status.PENDING)

    def test_kitchen_events_are_sent_after_commit(self):
        from unittest import mock

        self._add_to_table(self.table_1, quantity=1)
        with mock.patch('App_Sales.kitchen.notify_kitchen_changed') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self._send(self.table_1)
            with self.captureOnCommitCallbacks(execute=True):
                self._set_status(KitchenTicketItem.objects.get(), KitchenTicketItem.Status.DONE)
        reasons = [call.kwargs['reason'] for call in notify.call_args_list]
        self.assertEqual(reasons, ['created', 'done'])
        self.assertIn('Cà phê sữa x1 đã xong', notify.call_args_list[-1].kwargs['message'])

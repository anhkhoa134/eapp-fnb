"""FNB-11: đơn QR chờ duyệt tự huỷ sau 30 phút, tối đa 3 đơn chờ mỗi bàn."""
import json
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from App_Public import tests as public_tests
from App_Sales import qr_expiry
from App_Sales import tests as sales_tests
from App_Sales.models import QROrder, QROrderItem


def _age(order_id, minutes):
    QROrder.objects.filter(pk=order_id).update(created_at=timezone.now() - timedelta(minutes=minutes))


class PublicQrExpiryTests(TestCase):
    setUp = public_tests.PublicQrApiTests.setUp
    _create_pending_order = public_tests.PublicQrApiTests._create_pending_order

    def _post_order(self):
        payload = {
            'table_code': self.table.code, 'token': self.table.qr_token,
            'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 1}],
        }
        return self.client.post(
            reverse('App_Public_API:qr_orders_create'), data=json.dumps(payload), content_type='application/json'
        )

    def test_max_three_pending_orders_per_table(self):
        for _ in range(qr_expiry.QR_ORDER_MAX_PENDING_PER_TABLE):
            self._create_pending_order()
        res = self._post_order()
        self.assertEqual(res.status_code, 429)
        self.assertIn('đơn chờ quán duyệt', res.json()['detail'])
        self.assertEqual(QROrder.objects.filter(status=QROrder.Status.PENDING).count(), 3)

    def test_expired_order_frees_a_slot_and_shows_reason(self):
        ids = [self._create_pending_order() for _ in range(3)]
        _age(ids[0], 31)
        res = self._post_order()
        self.assertEqual(res.status_code, 201, res.content)
        expired = QROrder.objects.get(pk=ids[0])
        self.assertEqual(expired.status, QROrder.Status.REJECTED)
        self.assertEqual(expired.rejection_reason, qr_expiry.QR_ORDER_EXPIRED_REASON)
        self.assertIsNone(expired.rejected_by)
        self.assertIsNotNone(expired.resolved_at)

    def test_order_younger_than_30_minutes_stays_pending(self):
        order_id = self._create_pending_order()
        _age(order_id, 29)
        self.assertEqual(qr_expiry.expire_stale_qr_orders(), 0)
        self.assertEqual(QROrder.objects.get(pk=order_id).status, QROrder.Status.PENDING)

    def test_management_command_expires_stale_orders(self):
        order_id = self._create_pending_order()
        _age(order_id, 45)
        call_command('expire_qr_orders', verbosity=0)
        self.assertEqual(QROrder.objects.get(pk=order_id).status, QROrder.Status.REJECTED)


class PosQrExpiryTests(TestCase):
    setUp = sales_tests.SalesApiTests.setUp

    def _qr_order(self, minutes_old):
        order = QROrder.objects.create(
            tenant=self.tenant, store=self.store_1, table=self.table_1, status=QROrder.Status.PENDING,
        )
        QROrderItem.objects.create(
            qr_order=order, product=self.product, unit=self.unit,
            snapshot_product_name=self.product.name, snapshot_unit_name=self.unit.name,
            unit_price_snapshot=Decimal('25000'), quantity=1, line_total=Decimal('25000'),
        )
        _age(order.id, minutes_old)
        return order

    def test_cannot_approve_expired_order(self):
        order = self._qr_order(40)
        res = self.client.post(
            reverse('App_Sales_API:qr_order_approve', kwargs={'order_id': order.id}),
            data='{}', content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('quán chưa duyệt trong 30 phút', res.json()['detail'])
        order.refresh_from_db()
        self.assertEqual(order.status, QROrder.Status.REJECTED)

    def test_pending_list_hides_expired_orders(self):
        fresh = self._qr_order(5)
        self._qr_order(40)
        res = self.client.get(reverse('App_Sales_API:qr_orders'), {'store_id': self.store_1.id})
        self.assertEqual(res.status_code, 200)
        ids = [row['id'] for row in res.json()['orders']]
        self.assertEqual(ids, [fresh.id])

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.db import IntegrityError, connections
from django.test import Client, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from App_Accounts.models import RateLimit
from App_Public import views
from App_Sales.models import DiningTable, QROrder, QROrderItem
from App_Sales.tests_ops import OpsTestBase


class CreationPayloadMixin:
    def payload(self, mode='qr', **extra):
        body = {
            'client_request_id': str(uuid4()), 'note': 'Ít đá',
            'items': [{'product_id': self.product.id, 'unit_id': self.unit.id, 'quantity': 2}],
        }
        if mode == 'qr':
            body.update(table_code=self.table.code, token=self.table.qr_token)
        else:
            body.update(tenant_slug=self.tenant.public_slug, store_id=self.store.id,
                        customer_name='Khách thử', customer_phone='0901234567')
        return {**body, **extra}

    def create(self, payload, mode='qr', client=None):
        route = 'qr_orders_create' if mode == 'qr' else 'takeaway_orders_create'
        return (client or self.client).post(
            reverse(f'App_Public_API:{route}'), data=json.dumps(payload), content_type='application/json',
        )


class PublicOrderIdempotencyTests(CreationPayloadMixin, OpsTestBase):
    @patch('App_Public.views.notify_qr_order_changed')
    def test_retry_returns_existing_order_and_notifies_once(self, notify):
        body = self.payload()
        first = self.create(body)
        second = self.create(body)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()['qr_order_id'], second.json()['qr_order_id'])
        self.assertTrue(second.json()['replayed'])
        self.assertEqual(QROrder.objects.count(), 1)
        self.assertEqual(QROrderItem.objects.count(), 1)
        self.assertEqual(notify.call_count, 1)

    def test_replay_survives_menu_changes_order_resolution_and_ordering_closure(self):
        body = self.payload()
        order_id = self.create(body).json()['qr_order_id']
        QROrder.objects.filter(pk=order_id).update(status=QROrder.Status.APPROVED)
        self.product.is_active = False
        self.product.save()
        self.tenant.show_qr_order_feature = False
        self.tenant.save()
        response = self.create(body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], QROrder.Status.APPROVED)
        self.assertEqual(QROrder.objects.count(), 1)

    def test_changed_body_is_conflict_without_modifying_order(self):
        body = self.payload()
        self.create(body)
        response = self.create({**body, 'note': 'Khác'})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('order', response.json())
        self.assertEqual(QROrder.objects.get().customer_note, 'Ít đá')

    def test_retry_requires_valid_table_credentials(self):
        body = self.payload()
        self.create(body)
        self.assertEqual(self.create({**body, 'token': 'wrong'}).status_code, 403)
        other = DiningTable.objects.create(tenant=self.tenant, store=self.store, code='OTHER', name='Bàn khác')
        response = self.create({**body, 'table_code': other.code, 'token': other.qr_token})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('order', response.json())

    def test_takeaway_retry_returns_same_access_key_without_using_rate_quota(self):
        body = self.payload('takeaway')
        first = self.create(body, 'takeaway')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(RateLimit.objects.get().count, 1)
        RateLimit.objects.update(count=views.TAKEAWAY_ORDER_LIMIT_PER_IP)
        response = self.create(body, 'takeaway')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(first.json()['access_key'], response.json()['access_key'])
        self.assertEqual(first.json()['qr_order_id'], response.json()['qr_order_id'])
        self.assertEqual(RateLimit.objects.get().count, views.TAKEAWAY_ORDER_LIMIT_PER_IP)
        self.assertEqual(QROrder.objects.count(), 1)

    def test_takeaway_conflicts_do_not_disclose_access_key(self):
        body = self.payload('takeaway')
        self.create(body, 'takeaway')
        for change in [{'customer_phone': '0907654321'}, {'store_id': self.other_store.id}]:
            response = self.create({**body, **change}, 'takeaway')
            self.assertEqual(response.status_code, 409)
            self.assertNotIn('access_key', response.json())
        qr_body = self.payload(client_request_id=body['client_request_id'])
        self.assertEqual(self.create(qr_body).status_code, 409)

    def test_invalid_keys_are_rejected(self):
        for mode in ['qr', 'takeaway']:
            for key in ['', 'guessable', 123, str(uuid4()).replace('-', '') + 'x']:
                with self.subTest(mode=mode, key=key):
                    self.assertEqual(self.create(self.payload(mode, client_request_id=key), mode).status_code, 400)
        self.assertFalse(QROrder.objects.exists())

    def test_invalid_attempt_does_not_reserve_key(self):
        body = self.payload()
        self.assertEqual(self.create({**body, 'items': []}).status_code, 400)
        self.assertEqual(self.create(body).status_code, 201)

    def test_failed_insert_rolls_back_key_items_and_rate_counter(self):
        body = self.payload('takeaway')
        original_hit = views.rate_limit.hit

        def fail_after_rate_hit(*args, **kwargs):
            original_hit(*args, **kwargs)
            raise IntegrityError('Simulated transaction failure')

        with patch('App_Public.views.rate_limit.hit', side_effect=fail_after_rate_hit):
            with self.assertRaises(IntegrityError):
                self.create(body, 'takeaway')
        self.assertFalse(QROrder.objects.exists())
        self.assertFalse(QROrderItem.objects.exists())
        self.assertFalse(RateLimit.objects.exists())
        self.assertEqual(self.create(body, 'takeaway').status_code, 201)

    def test_new_key_allows_intentional_repeat_order_and_legacy_requests_still_work(self):
        for _ in range(2):
            self.assertEqual(self.create(self.payload()).status_code, 201)
        body = self.payload()
        del body['client_request_id']
        self.assertEqual(self.create(body).status_code, 201)
        self.assertEqual(self.create(body).status_code, 201)
        self.assertEqual(QROrder.objects.count(), 4)


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
@skipUnlessDBFeature('has_select_for_update')
class ConcurrentPublicOrderTests(CreationPayloadMixin, TransactionTestCase):
    setUp = OpsTestBase.setUp

    def concurrent_create(self, mode, *, conflicting=False):
        body = self.payload(mode)
        second_body = {**body, 'note': 'Nội dung khác'} if conflicting else body
        ready = Barrier(2)
        original_prepare = views._prepare_order_items

        def prepare(**kwargs):
            result = original_prepare(**kwargs)
            ready.wait(timeout=10)  # Both requests passed the initial replay check.
            return result

        def post(payload):
            try:
                return self.create(payload, mode, client=Client())
            finally:
                connections.close_all()

        with patch('App_Public.views._prepare_order_items', side_effect=prepare), patch(
            'App_Public.views.notify_qr_order_changed'
        ) as notify, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(post, body)
            second = pool.submit(post, second_body)
            responses = [first.result(timeout=15), second.result(timeout=15)]
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409] if conflicting else [200, 201])
        self.assertEqual(QROrder.objects.count(), 1)
        self.assertEqual(QROrderItem.objects.count(), 1)
        self.assertEqual(notify.call_count, 1)
        if not conflicting:
            self.assertEqual(responses[0].json()['qr_order_id'], responses[1].json()['qr_order_id'])
        if mode == 'takeaway':
            self.assertEqual(RateLimit.objects.get().count, 1)
            if not conflicting:
                self.assertEqual(responses[0].json()['access_key'], responses[1].json()['access_key'])

    def test_concurrent_qr_requests_create_one_order(self):
        self.concurrent_create('qr')

    def test_concurrent_takeaway_requests_create_one_order(self):
        self.concurrent_create('takeaway')

    def test_concurrent_conflicting_requests_create_one_order(self):
        self.concurrent_create('takeaway', conflicting=True)

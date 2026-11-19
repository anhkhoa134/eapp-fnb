"""SePay webhook contract, chạy với adapter thật của từng app (giống tests.py)."""
import hashlib
import hmac
import json
import time
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from . import sepay, services
from .models import PaymentAttempt, SubscriptionRequest
from . import tests as base

SECRET = 'test-sepay-secret'
ACCOUNT = '0123456789'
SEPAY_ON = dict(SEPAY_WEBHOOK_HMAC_SECRET=SECRET, SEPAY_BANK_ACCOUNT=ACCOUNT, SEPAY_BANK_CODE='vietinbank',
                SEPAY_ACCOUNT_HOLDER='CONG TY EAPP', BILLING_PAYMENT_PROVIDERS=('sepay',))


@override_settings(**SEPAY_ON)
class SepayWebhookTests(TestCase):
    # Dùng lại fixture của tests.BillingTests (không kế thừa để không chạy lại các test đó).
    make_user = base.BillingTests.make_user
    payload = base.BillingTests.payload
    submit = base.BillingTests.submit
    expiry = base.BillingTests.expiry

    def setUp(self):
        base.BillingTests.setUp(self)
        self.sepay_client = Client(enforce_csrf_checks=True)  # SePay gọi server-tới-server, không có CSRF token

    def event(self, item, **kwargs):
        return {'id': 9001, 'gateway': 'VietinBank', 'accountNumber': ACCOUNT, 'subAccount': None,
                'code': None, 'content': f'{sepay.transfer_content(item.reference)} chuyen tien',
                'transferType': 'in', 'transferAmount': item.amount_vnd, 'referenceCode': 'FT1', **kwargs}

    def post(self, body, *, secret=SECRET, timestamp=None, signature=None):
        raw = json.dumps(body).encode()
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        if signature is None:
            signature = 'sha256=' + hmac.new(secret.encode(), f'{timestamp}.'.encode() + raw, hashlib.sha256).hexdigest()
        return self.sepay_client.post(reverse('billing:sepay_webhook'), raw, content_type='application/json',
                                HTTP_X_SEPAY_SIGNATURE=signature, HTTP_X_SEPAY_TIMESTAMP=timestamp,
                                HTTP_USER_AGENT='python-requests/2.31')

    def status(self, item):
        item.refresh_from_db()
        return item.status

    def test_paid_transfer_activates_once(self):
        item = self.submit()
        self.client.logout()
        response = self.post(self.event(item))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'success': True})
        self.assertEqual(self.status(item), 'approved')
        payment = item.payments.get(provider='sepay')
        self.assertEqual((payment.status, payment.provider_reference, payment.received_amount_vnd), ('succeeded', '9001', item.amount_vnd))
        self.assertEqual(item.payments.get(provider='manual').status, 'cancelled')
        end = self.expiry()
        self.assertEqual(self.post(self.event(item)).status_code, 200)  # SePay gửi lại
        self.assertEqual(self.expiry(), end)
        self.assertEqual(PaymentAttempt.objects.filter(provider='sepay', status='succeeded').count(), 1)

    def test_bank_mangled_content_still_matches(self):
        item = self.submit()
        ref = item.reference.lower()
        self.post(self.event(item, content=f'MBVCB.123.{ref[:3]} {ref[3:]}.CT tu 0123'))
        self.assertEqual(self.status(item), 'approved')

    def test_rejects_bad_signature_replay_and_missing_secret(self):
        item = self.submit()
        self.assertEqual(self.post(self.event(item), secret='wrong').status_code, 401)
        self.assertEqual(self.post(self.event(item), timestamp=int(time.time()) - 3600).status_code, 401)
        self.assertEqual(self.post(self.event(item), signature='sha256=00').status_code, 401)
        with override_settings(SEPAY_WEBHOOK_HMAC_SECRET=''):
            self.assertEqual(self.post(self.event(item)).status_code, 401)
        self.assertEqual(self.status(item), 'pending')

    @override_settings(BILLING_PAYMENT_PROVIDERS=())
    def test_disabled_without_configuration(self):
        item = self.submit()
        self.assertEqual(self.post(self.event(item)).status_code, 404)
        self.assertIsNone(sepay.payment_info(item))
        self.assertEqual(self.status(item), 'pending')

    def test_ignores_wrong_direction_account_amount_and_other_apps(self):
        item = self.submit()
        for change in ({'transferType': 'out'}, {'accountNumber': '999999'}, {'transferAmount': item.amount_vnd - 1},
                       {'transferAmount': 'abc'}, {'id': ''}, {'content': 'SEVQR DH000093'},
                       {'content': 'SEVQR XYZ0123456789ABCDEF'}):
            with self.subTest(change=change):
                response = self.post(self.event(item, **change))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.status(item), 'pending')
        self.assertFalse(PaymentAttempt.objects.filter(provider='sepay', status='succeeded').exists())

    def test_virtual_sub_account_and_overpay_are_accepted(self):
        item = self.submit()
        self.post(self.event(item, accountNumber='111', subAccount=ACCOUNT, transferAmount=item.amount_vnd + 1000))
        self.assertEqual(self.status(item), 'approved')
        self.assertEqual(item.payments.get(provider='sepay').received_amount_vnd, item.amount_vnd + 1000)

    def test_cancelled_or_unknown_request_is_not_activated(self):
        item = self.submit()
        services.cancel_request(self.request, item.pk)
        with self.assertLogs('App_Billing.views', 'ERROR'):
            self.assertEqual(self.post(self.event(item)).status_code, 200)
        self.assertEqual(self.status(item), 'cancelled')
        prefix = item.reference[:-16]
        ghost = SubscriptionRequest(reference=prefix + ('F' * 16 if item.reference[-16:] != 'F' * 16 else 'E' * 16), amount_vnd=1)
        with self.assertLogs('App_Billing.views', 'ERROR'):
            self.assertEqual(self.post(self.event(ghost, id=9100)).status_code, 200)

    def test_same_transaction_cannot_pay_two_requests(self):
        item = self.submit()
        self.post(self.event(item))
        second = self.submit()
        self.post(self.event(second))  # cùng id 9001: coi như SePay gửi lại, không kích hoạt yêu cầu khác
        self.assertEqual(self.status(second), 'pending')
        self.post(self.event(second, id=9002))
        self.assertEqual(self.status(second), 'approved')

    def test_contact_price_request_has_no_qr(self):
        item = self.submit(plan_key=self.contact['key'])
        self.assertIsNone(sepay.payment_info(item))

    def test_history_shows_qr_only_while_pending(self):
        item = self.submit()
        data = self.client.get(self.url).json()['items'][0]
        self.assertEqual(data['payment']['content'], f'SEVQR {item.reference}')
        self.assertIn('qr.sepay.vn/img?acc=0123456789&bank=vietinbank', data['payment']['qr_url'])
        self.assertIn(f'amount={item.amount_vnd}', data['payment']['qr_url'])
        self.post(self.event(item))
        self.assertIsNone(self.client.get(self.url).json()['items'][0]['payment'])

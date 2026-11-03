"""Run the same lifecycle contract against each application's real subscription adapter."""
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from . import adapter, services
from .forms import ReviewForm
from .models import PaymentAttempt, SubscriptionRequest


class BillingTests(TestCase):
    def make_user(self, name):
        User = get_user_model()
        kwargs = {User.USERNAME_FIELD: f'{name}@example.test' if User.USERNAME_FIELD == 'email' else name}
        if settings.BILLING_APPLICATION in ('pos', 'fnb'):
            from App_Tenant.models import Tenant
            slug_field = 'public_slug' if settings.BILLING_APPLICATION == 'fnb' else 'slug'
            tenant = Tenant.objects.create(name=name, **{slug_field: name})
            kwargs.update(tenant=tenant, role=User.Role.MANAGER)
        return User.objects.create_user(password='billing-test-password', **kwargs)

    def setUp(self):
        self.user = self.make_user('billing-owner')
        self.other = self.make_user('billing-other')
        self.admin = self.make_user('billing-admin')
        self.admin.is_superuser = self.admin.is_staff = True
        self.admin.save()
        self.request = SimpleNamespace(user=self.user)
        self.account = adapter.account_for(self.request)
        self.paid = next(p for p in adapter.plans() if p['month'] and p['year'])
        self.contact = next(p for p in adapter.plans() if p['month'] is None)
        self.client.force_login(self.user)
        self.url = reverse('billing:requests')

    def payload(self, **kwargs):
        return {'plan_key': self.paid['key'], 'billing_cycle': 'month', 'customer_note': '', 'client_token': str(uuid.uuid4()), **kwargs}

    def submit(self, **kwargs):
        data = self.payload(**kwargs)
        data['client_token'] = uuid.UUID(data['client_token'])
        return services.submit_request(self.request, **data)

    def expiry(self):
        app = settings.BILLING_APPLICATION
        if app == 'pm':
            from App_Accounts.models import UserSubscription
            return UserSubscription.objects.get(user=self.user, status='active').ended_at
        if app == 'photo':
            from App_Accounts.models import Photographer
            from App_Subscription.models import get_active_subscription
            return get_active_subscription(Photographer.objects.get(user=self.user)).end_date
        self.account.refresh_from_db()
        return getattr(self.account, 'subscription_ends_on' if app == 'fnb' else 'subscription_expires_on')

    def test_submit_snapshot_ignores_client_price_and_replay(self):
        data = self.payload(amount_vnd='1', account_id=str(self.other.pk))
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 201, response.content)
        item = SubscriptionRequest.objects.get()
        self.assertEqual(item.amount_vnd, self.paid['month'])
        self.assertEqual(item.account_id, self.account.pk)
        self.assertEqual(item.payments.get().expected_amount_vnd, self.paid['month'])
        self.assertEqual(self.client.post(self.url, data).status_code, 201)
        self.assertEqual(SubscriptionRequest.objects.count(), 1)
        services.review_request(item.pk, self.admin, decision='approved')
        end = self.expiry()
        self.assertEqual(self.client.post(self.url, data).status_code, 201)
        self.assertEqual(self.expiry(), end)

    def test_history_and_cancel_are_scoped(self):
        item = self.submit()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).json()['items'], [])
        cancel = reverse('billing:cancel', args=[item.pk])
        self.assertEqual(self.client.post(cancel).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).json()['items'][0]['id'], str(item.pk))
        self.assertEqual(self.client.post(cancel).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'cancelled')
        self.assertEqual(item.payments.get().status, 'cancelled')
        self.assertEqual(self.client.post(cancel).status_code, 400)

    def test_auth_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, self.payload()).status_code, 403)

    def test_staff_cannot_manage_tenant_billing(self):
        if settings.BILLING_APPLICATION not in ('fnb', 'pos'):
            return
        self.user.role = self.user.Role.STAFF
        self.user.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)

    def test_invalid_fields_and_one_pending(self):
        for changes in ({'plan_key': 'missing'}, {'billing_cycle': 'week'}, {'client_token': 'bad'}, {'customer_note': 'x' * 2001}):
            with self.subTest(changes=list(changes)):
                self.assertEqual(self.client.post(self.url, self.payload(**changes)).status_code, 400)
        self.submit()
        self.assertEqual(self.client.post(self.url, self.payload(billing_cycle='year')).status_code, 400)
        self.assertEqual(SubscriptionRequest.objects.count(), 1)

    def test_month_approval_and_year_renewal_preserve_remaining_time(self):
        item = self.submit()
        services.review_request(item.pk, self.admin, decision='approved', note='Đã nhận thanh toán')
        item.refresh_from_db()
        self.assertEqual(item.status, 'approved')
        self.assertEqual(item.payments.get().status, 'succeeded')
        self.account.refresh_from_db()
        self.assertEqual(adapter.current_plan_key(self.account), self.paid['key'])
        end = self.expiry()
        today = timezone.localdate()
        if settings.BILLING_APPLICATION == 'pm':
            self.assertEqual(timezone.localtime(end).date(), services.add_months(today, 1))
        else:
            self.assertEqual(end, services.add_months(today, 1) - timedelta(days=1))
        renewal = self.submit(billing_cycle='year')
        self.assertEqual(renewal.kind, 'renewal')
        self.assertEqual(renewal.amount_vnd, self.paid['year'])
        services.review_request(renewal.pk, self.admin, decision='approved')
        expected = services.add_months(timezone.localtime(end), 12) if settings.BILLING_APPLICATION == 'pm' else services.add_months(end + timedelta(days=1), 12) - timedelta(days=1)
        self.assertEqual(self.expiry(), expected)
        with self.assertRaises(ValidationError):
            services.review_request(renewal.pk, self.admin, decision='approved')
        self.assertEqual(self.expiry(), expected)

    def test_approval_permissions_and_snapshot_amount(self):
        item = self.submit()
        with self.assertRaises(PermissionDenied):
            services.review_request(item.pk, self.user, decision='approved')
        with self.assertRaises(ValidationError):
            services.review_request(item.pk, self.admin, decision='approved', confirmed_amount=1)
        item.refresh_from_db()
        self.assertEqual(item.status, 'pending')
        services.review_request(item.pk, self.admin, decision='rejected', note='Cần bổ sung thông tin')
        item.refresh_from_db()
        self.assertIsNone(item.activated_at)
        self.assertEqual(item.payments.get().status, 'cancelled')

    def test_contact_quote_is_required(self):
        item = self.submit(plan_key=self.contact['key'])
        self.assertIsNone(item.amount_vnd)
        with self.assertRaises(ValidationError):
            services.review_request(item.pk, self.admin, decision='approved')
        services.review_request(item.pk, self.admin, decision='approved', confirmed_amount=5000000)
        item.refresh_from_db()
        self.assertEqual(item.approved_amount_vnd, 5000000)
        self.account.refresh_from_db()
        self.assertEqual(adapter.current_plan_key(self.account), self.contact['key'])

    def test_admin_review_requires_confirmation(self):
        item = self.submit()
        url = reverse('admin:billing_request_review', args=[item.pk])
        self.client.force_login(self.admin)
        response = self.client.post(url, {'decision': 'approved', 'confirmed_amount': item.amount_vnd})
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual(item.status, 'pending')
        response = self.client.post(url, {'decision': 'approved', 'confirmed_amount': item.amount_vnd, 'payment_confirmed': 'on'})
        self.assertEqual(response.status_code, 302, response.content)
        item.refresh_from_db()
        self.assertEqual(item.status, 'approved')
        self.assertFalse(ReviewForm({'decision': 'approved'}).is_valid())

    def test_manual_receipt_cannot_use_provider_boundary(self):
        item = self.submit()
        with self.assertRaises(ValidationError):
            services.record_verified_payment(item.payments.get().pk, transaction_id='tx', amount_vnd=item.amount_vnd)
        with self.assertRaises(ValidationError):
            services.create_payment_attempt(item.pk, provider='sepay')

    @override_settings(BILLING_PAYMENT_PROVIDERS=('test-provider',))
    def test_verified_payment_is_idempotent_and_validates_amount(self):
        item = self.submit()
        payment = services.create_payment_attempt(item.pk, provider='test-provider')
        self.assertEqual(services.create_payment_attempt(item.pk, provider='test-provider').pk, payment.pk)
        for amount, currency in ((1, 'VND'), (item.amount_vnd, 'USD'), (True, 'VND')):
            with self.assertRaises(ValidationError):
                services.record_verified_payment(payment.pk, transaction_id='tx-1', amount_vnd=amount, currency=currency)
        services.record_verified_payment(payment.pk, transaction_id='tx-1', amount_vnd=item.amount_vnd)
        end = self.expiry()
        services.record_verified_payment(payment.pk, transaction_id='tx-1', amount_vnd=item.amount_vnd)
        self.assertEqual(self.expiry(), end)
        self.assertEqual(item.payments.get(provider='manual').status, 'cancelled')
        second = self.submit()
        second_payment = services.create_payment_attempt(second.pk, provider='test-provider')
        with self.assertRaises(ValidationError):
            services.record_verified_payment(second_payment.pk, transaction_id='tx-1', amount_vnd=second.amount_vnd)
        services.cancel_request(self.request, second.pk)
        with self.assertRaises(ValidationError):
            services.record_verified_payment(second_payment.pk, transaction_id='tx-2', amount_vnd=second.amount_vnd)

    def test_calendar_month_end(self):
        self.assertEqual(services.add_months(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(services.add_months(date(2028, 2, 29), 12), date(2029, 2, 28))

    def test_account_page_renders_request_modal_and_history(self):
        app = settings.BILLING_APPLICATION
        if app == 'pm':
            from App_Accounts.models import TenantMembership
            from App_Core.models import Tenant
            tenant = Tenant.objects.create(code='billing-ui', name='Billing UI', slug='billing-ui')
            TenantMembership.objects.create(user=self.user, tenant=tenant, role='owner', status='active', is_default=True)
            url = reverse('pm:dashboard') + '?tab=settings'
        else:
            url = reverse({'fnb': 'App_Quanly:account', 'pos': 'App_Accounts:account', 'photo': 'accounts:pricing'}[app])
        item = self.submit()
        response = self.client.get(url)
        self.assertContains(response, 'Chọn gói này', count=4)
        self.assertContains(response, 'id="billingRequestModal"', count=1)
        self.assertContains(response, 'Lịch sử yêu cầu')
        self.assertContains(response, item.reference)
        self.assertContains(response, services.money(item.amount_vnd))

    def test_free_plan_approval_removes_paid_entitlements(self):
        item = self.submit()
        services.review_request(item.pk, self.admin, decision='approved')
        free = next(p for p in adapter.plans() if p['month'] == 0 and p['year'] == 0)
        change = self.submit(plan_key=free['key'])
        services.review_request(change.pk, self.admin, decision='approved')
        self.account.refresh_from_db()
        self.assertEqual(adapter.current_plan_key(self.account), free['key'])
        change.refresh_from_db()
        self.assertEqual(change.approved_amount_vnd, 0)
        if settings.BILLING_APPLICATION in ('pm', 'pos', 'fnb'):
            self.assertIsNone(self.expiry())

    @override_settings(BILLING_PAYMENT_PROVIDERS=('test-provider',))
    def test_payment_cannot_override_request_quote(self):
        item = self.submit()
        payment = services.create_payment_attempt(item.pk, provider='test-provider')
        payment.expected_amount_vnd = 1
        payment.save(update_fields=['expected_amount_vnd'])
        with self.assertRaises(ValidationError):
            services.record_verified_payment(payment.pk, transaction_id='bad-quote', amount_vnd=1)
        item.refresh_from_db()
        self.assertEqual(item.status, 'pending')

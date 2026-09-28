from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import User
from App_Sales.models import Customer
from App_Tenant.models import Store, Tenant, UserStoreAccess
from Project.asgi import application


class TenantAccessTestBase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Access Tenant', public_slug='access-tenant')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.manager = User.objects.create_user(
            username='access_manager', password='123456', tenant=self.tenant, role=User.Role.MANAGER
        )
        self.staff = User.objects.create_user(
            username='access_staff', password='123456', tenant=self.tenant, role=User.Role.STAFF
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

    def _set_ends_on(self, days_from_today):
        self.tenant.subscription_ends_on = timezone.localdate() + timedelta(days=days_from_today)
        self.tenant.save(update_fields=['subscription_ends_on'])

    def _login_post(self, username):
        return self.client.post(reverse('App_Accounts:login'), {'username': username, 'password': '123456'})

    def _is_logged_in(self):
        return '_auth_user_id' in self.client.session


class InactiveTenantAccessTests(TenantAccessTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)
        Tenant.objects.filter(pk=self.tenant.pk).update(is_active=False)

    def test_pos_page_logs_out_and_redirects_to_login(self):
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertRedirects(res, reverse('App_Accounts:login'), fetch_redirect_response=False)
        self.assertFalse(self._is_logged_in())

    def test_quanly_logs_out_and_redirects_to_login(self):
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertRedirects(res, reverse('App_Accounts:login'), fetch_redirect_response=False)
        self.assertFalse(self._is_logged_in())

    def test_pos_api_returns_403_json(self):
        res = self.client.get(reverse('App_Sales_API:products'))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 'tenant_inactive')

    def test_login_rejected(self):
        self.client.logout()
        res = self._login_post('access_staff')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Doanh nghiệp đã ngừng hoạt động')
        self.assertFalse(self._is_logged_in())


class ExpiredSubscriptionAccessTests(TenantAccessTestBase):
    def setUp(self):
        super().setUp()
        self._set_ends_on(-1)

    def test_manager_pos_redirects_to_account(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertRedirects(res, reverse('App_Quanly:account'), fetch_redirect_response=False)
        self.assertTrue(self._is_logged_in())

    def test_manager_can_view_quanly_with_expired_banner(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Gói dịch vụ đã hết hạn')

    def test_manager_can_open_account_page(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:account'))
        self.assertEqual(res.status_code, 200)

    def test_manager_write_on_quanly_is_blocked(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse('App_Quanly:customers'),
            {'name': 'Khách A', 'phone': '0901234567', 'is_active': 'on'},
        )
        self.assertRedirects(res, reverse('App_Quanly:account'), fetch_redirect_response=False)
        self.assertFalse(Customer.objects.filter(tenant=self.tenant).exists())

    def test_pos_api_returns_403_json(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Sales_API:products'))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 'subscription_expired')

    def test_staff_on_pos_is_logged_out(self):
        self.client.force_login(self.staff)
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertRedirects(res, reverse('App_Accounts:login'), fetch_redirect_response=False)
        self.assertFalse(self._is_logged_in())

    def test_staff_login_rejected_manager_login_allowed(self):
        res = self._login_post('access_staff')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Gói dịch vụ của cửa hàng đã hết hạn')
        self.assertFalse(self._is_logged_in())

        res = self._login_post('access_manager')
        self.assertEqual(res.status_code, 302)
        self.assertTrue(self._is_logged_in())

    def test_ends_today_is_not_expired(self):
        self._set_ends_on(0)
        self.client.force_login(self.staff)
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 200)


class ExpiringSoonSubscriptionTests(TenantAccessTestBase):
    def test_warning_banner_within_7_days(self):
        self._set_ends_on(3)
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Gói dịch vụ còn 3 ngày')
        self.assertEqual(self.client.get(reverse('App_Sales:pos')).status_code, 200)

    def test_no_banner_when_far_from_expiry(self):
        self._set_ends_on(30)
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertNotContains(res, 'Gói dịch vụ còn')

    def test_no_banner_without_end_date(self):
        Tenant.objects.filter(pk=self.tenant.pk).update(subscription_ends_on=None)
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertNotContains(res, 'Gói dịch vụ')


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class BlockedTenantWebSocketTests(TenantAccessTestBase):
    def _can_connect(self):
        self.client.force_login(self.staff)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value

        async def scenario():
            ws = WebsocketCommunicator(
                application,
                f'/ws/pos/store/{self.store.id}/',
                headers=[(b'cookie', f'{settings.SESSION_COOKIE_NAME}={cookie}'.encode('utf-8'))],
            )
            connected, _ = await ws.connect()
            if connected:
                await ws.disconnect()
            return connected

        return async_to_sync(scenario)()

    def test_ws_allowed_for_active_tenant(self):
        self.assertTrue(self._can_connect())

    def test_ws_rejected_for_inactive_tenant(self):
        Tenant.objects.filter(pk=self.tenant.pk).update(is_active=False)
        self.assertFalse(self._can_connect())

    def test_ws_rejected_for_expired_subscription(self):
        self._set_ends_on(-1)
        self.assertFalse(self._can_connect())

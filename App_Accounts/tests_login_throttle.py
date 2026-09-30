from datetime import timedelta

from django.contrib.admin.sites import site
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_Accounts.admin import LoginAttemptAdmin
from App_Accounts.login_throttle import get_client_ip
from App_Accounts.models import LoginAttempt, User
from App_Tenant.models import Store, Tenant, UserStoreAccess


@override_settings(LOGIN_TRUST_X_REAL_IP=True)
class ClientIpTests(SimpleTestCase):
    def test_trusted_ip_and_identical_proxy_duplicates(self):
        for header, expected in [
            ('203.0.113.5', '203.0.113.5'),
            ('203.0.113.5,203.0.113.5', '203.0.113.5'),
            (' 203.0.113.5, 203.0.113.5 ', '203.0.113.5'),
            ('2001:db8::1', '2001:db8::1'),
            ('2001:db8::1, 2001:0db8::1', '2001:db8::1'),
        ]:
            with self.subTest(header=header):
                request = RequestFactory().get('/', HTTP_X_REAL_IP=header)
                self.assertEqual(get_client_ip(request), expected)

    def test_invalid_or_ambiguous_header_falls_back_to_peer(self):
        for header in ['', 'unknown', '203.0.113.5:443', '203.0.113.5, unknown',
                       '203.0.113.5, 203.0.113.6', 'fe80::1%eth0']:
            with self.subTest(header=header):
                request = RequestFactory().get('/', HTTP_X_REAL_IP=header, REMOTE_ADDR='127.0.0.1')
                self.assertEqual(get_client_ip(request), '127.0.0.1')

    def test_missing_or_invalid_peer_returns_empty_ip(self):
        for peer in ['', 'unix:', 'unknown', '127.0.0.1,127.0.0.1']:
            with self.subTest(peer=peer):
                request = RequestFactory().get('/', REMOTE_ADDR=peer)
                self.assertEqual(get_client_ip(request), '')
        self.assertEqual(get_client_ip(None), '')

    @override_settings(LOGIN_TRUST_X_REAL_IP=False)
    def test_untrusted_proxy_headers_are_ignored(self):
        request = RequestFactory().get(
            '/', HTTP_X_REAL_IP='203.0.113.5', HTTP_X_FORWARDED_FOR='203.0.113.6',
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(get_client_ip(request), '127.0.0.1')


@override_settings(LOGIN_FAILURE_LIMIT=3, LOGIN_LOCKOUT_MINUTES=15, LOGIN_TRUST_X_REAL_IP=False)
class LoginThrottleTests(TestCase):
    def setUp(self):
        tenant = Tenant.objects.create(name='Throttle', public_slug='throttle')
        store = Store.objects.create(tenant=tenant, name='Store 1', is_default=True)
        self.user = User.objects.create_user(
            username='throttle_user', password='dung-mat-khau', tenant=tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.user, store=store, is_default=True)

    def _login(self, password, username='throttle_user', ip='10.0.0.1'):
        return self.client.post(
            reverse('App_Accounts:login'),
            {'username': username, 'password': password},
            REMOTE_ADDR=ip,
        )

    def _fail(self, times, **kwargs):
        for _ in range(times):
            self._login('sai', **kwargs)

    def test_locked_after_limit_even_with_correct_password(self):
        self._fail(3)
        res = self._login('dung-mat-khau')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'nhập sai quá nhiều lần')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_below_limit_can_still_login_and_counter_resets(self):
        self._fail(2)
        res = self._login('dung-mat-khau')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(LoginAttempt.objects.exists())

    def test_username_is_case_insensitive_for_lock(self):
        self._fail(3, username='THROTTLE_USER')
        res = self._login('dung-mat-khau')
        self.assertContains(res, 'nhập sai quá nhiều lần')

    def test_other_ip_is_not_locked(self):
        self._fail(3)
        res = self._login('dung-mat-khau', ip='10.0.0.2')
        self.assertEqual(res.status_code, 302)

    def test_lock_expires(self):
        self._fail(3)
        LoginAttempt.objects.update(locked_until=timezone.now() - timedelta(seconds=1))
        res = self._login('dung-mat-khau')
        self.assertEqual(res.status_code, 302)

    def test_unknown_username_gets_same_error_as_wrong_password(self):
        wrong_password = self._login('sai').context['form'].non_field_errors()
        unknown_user = self._login('sai', username='khong_ton_tai', ip='10.0.0.9').context['form'].non_field_errors()
        self.assertEqual(list(wrong_password), list(unknown_user))

    def test_unknown_username_is_also_locked(self):
        self._fail(3, username='khong_ton_tai')
        res = self._login('sai', username='khong_ton_tai')
        self.assertContains(res, 'nhập sai quá nhiều lần')

    def test_admin_unlock_action(self):
        self._fail(3)
        admin = LoginAttemptAdmin(LoginAttempt, site)
        request = RequestFactory().post('/')
        request._messages = type('M', (), {'add': lambda *a, **k: None})()
        admin.unlock(request, LoginAttempt.objects.all())
        res = self._login('dung-mat-khau')
        self.assertEqual(res.status_code, 302)

    @override_settings(LOGIN_TRUST_X_REAL_IP=True)
    def test_x_real_ip_used_when_trusted(self):
        self._fail(3)  # REMOTE_ADDR 10.0.0.1, không có X-Real-IP
        res = self.client.post(
            reverse('App_Accounts:login'),
            {'username': 'throttle_user', 'password': 'dung-mat-khau'},
            REMOTE_ADDR='10.0.0.1',
            HTTP_X_REAL_IP='203.0.113.5',
        )
        self.assertEqual(res.status_code, 302)

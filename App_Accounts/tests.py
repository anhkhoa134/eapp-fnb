import re
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import LoginAttempt, RateLimit, User
from App_Tenant.models import Store, Tenant, UserStoreAccess


class AccountUiTests(TestCase):
    def test_login_page_contains_base_containers(self):
        res = self.client.get(reverse('App_Accounts:login'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('id="spinnerContainer"', html)
        self.assertIn('id="toastContainer"', html)
        self.assertIn('id="commonModal"', html)


class LogoutSecurityTests(TestCase):
    def setUp(self):
        tenant = Tenant.objects.create(name='Demo Logout', public_slug='demo-logout')
        store = Store.objects.create(tenant=tenant, name='Store 1', is_default=True)
        self.user = User.objects.create_user(
            username='manager_logout',
            password='123456',
            tenant=tenant,
            role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=self.user, store=store, is_default=True)

    def test_logout_get_method_not_allowed(self):
        self.client.login(username='manager_logout', password='123456')
        res = self.client.get(reverse('App_Accounts:logout'))
        self.assertEqual(res.status_code, 405)

    def test_logout_post_success(self):
        self.client.login(username='manager_logout', password='123456')
        res = self.client.post(reverse('App_Accounts:logout'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('App_Accounts:login'), res.url)

        protected = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(protected.status_code, 302)
        self.assertIn(reverse('App_Accounts:login'), protected.url)


class SignupTests(TestCase):
    def _post_signup(self, **overrides):
        data = {
            'store_name': 'Cà phê Góc Phố',
            'username': 'gocpho',  # form tự thêm hậu tố _quanly
            'email': 'gocpho@example.com',
            'password1': 'GocPho@2026',
            'password2': 'GocPho@2026',
        }
        data.update(overrides)
        return self.client.post(reverse('App_Accounts:signup'), data)

    def test_login_page_links_to_signup(self):
        html = self.client.get(reverse('App_Accounts:login')).content.decode('utf-8')
        self.assertIn(reverse('App_Accounts:signup'), html)

    def test_signup_creates_free_tenant_with_single_manager(self):
        res = self._post_signup()
        self.assertRedirects(res, reverse('App_Quanly:products'))

        user = User.objects.get(username='gocpho_quanly')
        tenant = user.tenant
        self.assertEqual(user.role, User.Role.MANAGER)
        self.assertEqual(tenant.name, 'Cà phê Góc Phố')
        self.assertEqual(tenant.public_slug, 'ca-phe-goc-pho')
        self.assertEqual(tenant.subscription_plan.slug, 'mien-phi')
        self.assertIsNone(tenant.subscription_ends_on)
        self.assertEqual(tenant.max_staff_users, 0)
        self.assertEqual(tenant.max_products, tenant.subscription_plan.max_products)
        self.assertFalse(tenant.show_qr_order_feature)
        self.assertFalse(tenant.show_kitchen_feature)
        self.assertEqual(User.objects.filter(tenant=tenant).count(), 1)
        self.assertEqual(Store.objects.filter(tenant=tenant, is_default=True).count(), 1)
        self.assertEqual(tenant.dining_table_count(), 5)
        self.assertTrue(UserStoreAccess.objects.filter(user=user, is_default=True).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_signup_rejects_duplicate_username_and_mismatched_password(self):
        tenant = Tenant.objects.create(name='Existing', public_slug='existing')
        User.objects.create_user(username='taken_quanly', password='x', tenant=tenant, role=User.Role.MANAGER)

        res = self._post_signup(username='TAKEN_quanly', password2='Other@2026')
        self.assertEqual(res.status_code, 200)
        form = res.context['form']
        self.assertIn('username', form.errors)
        self.assertIn('password2', form.errors)
        self.assertEqual(Tenant.objects.count(), 1)

    def test_signup_public_slug_avoids_reserved_and_existing(self):
        Tenant.objects.create(name='Other', public_slug='quanly-2')
        self._post_signup(store_name='Quanly', username='a_quanly')
        self.client.logout()
        self._post_signup(store_name='Quanly', username='b_quanly')
        slugs = set(Tenant.objects.exclude(public_slug='quanly-2').values_list('public_slug', flat=True))
        self.assertEqual(slugs, {'quanly-3', 'quanly-4'})

    def test_authenticated_user_redirected_from_signup(self):
        self._post_signup()
        res = self.client.get(reverse('App_Accounts:signup'))
        self.assertRedirects(res, reverse('App_Sales:pos'), fetch_redirect_response=False)

    def test_signup_lowercases_username_and_saves_email(self):
        self._post_signup(username='GocPho', email='GocPho@Example.com')
        user = User.objects.get(username='gocpho_quanly')
        self.assertEqual(user.email, 'gocpho@example.com')

    def test_signup_requires_email(self):
        res = self._post_signup(email='')
        self.assertIn('email', res.context['form'].errors)
        self.assertFalse(User.objects.exists())

    def test_signup_rejects_demo_username(self):
        res = self._post_signup(username='DEMO')
        self.assertIn('username', res.context['form'].errors)

    def test_signup_long_store_name_gets_slug_within_limit(self):
        long_name = 'Quán ' + 'a' * 115
        self._post_signup(store_name=long_name, username='dai1')
        self.client.logout()
        self._post_signup(store_name=long_name, username='dai2')
        slugs = list(Tenant.objects.values_list('public_slug', flat=True))
        self.assertEqual(len(slugs), 2)
        self.assertEqual(len(set(slugs)), 2)
        self.assertTrue(all(len(slug) <= 120 for slug in slugs))

    def test_signup_rejects_store_name_exceeding_database_limit(self):
        res = self._post_signup(store_name='a' * 121)
        self.assertIn('store_name', res.context['form'].errors)
        self.assertFalse(User.objects.exists())

    @override_settings(SIGNUP_LIMIT_PER_IP=2, LOGIN_TRUST_X_REAL_IP=False)
    def test_signup_rate_limited_per_ip(self):
        for idx in range(2):
            self._post_signup(username=f'quan{idx}')
            self.client.logout()
        res = self._post_signup(username='quan9')
        self.assertEqual(res.status_code, 200)
        self.assertIn('quá nhiều tài khoản', ' '.join(res.context['form'].non_field_errors()))
        self.assertEqual(Tenant.objects.count(), 2)

    def test_signup_concurrent_duplicate_shows_form_error(self):
        def create_then_fail(**kwargs):
            tenant = Tenant.objects.create(name='Race', public_slug='race')
            User.objects.create_user(username=kwargs['username'], password='x', tenant=tenant)
            raise IntegrityError('duplicate')

        with mock.patch('App_Accounts.views.register_free_tenant', side_effect=create_then_fail):
            res = self._post_signup()
        self.assertEqual(res.status_code, 200)
        self.assertIn('username', res.context['form'].errors)


@override_settings(LOGIN_TRUST_X_REAL_IP=False)
class LoginFlowTests(TestCase):
    def setUp(self):
        tenant = Tenant.objects.create(name='Flow', public_slug='flow')
        store = Store.objects.create(tenant=tenant, name='Store 1', is_default=True)
        self.user = User.objects.create_user(
            username='flow_quanly', password='Flow@2026', tenant=tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.user, store=store, is_default=True)

    def _login(self, username='flow_quanly', password='Flow@2026', url=None, ip='10.0.0.1'):
        return self.client.post(
            url or reverse('App_Accounts:login'), {'username': username, 'password': password}, REMOTE_ADDR=ip
        )

    def test_login_username_is_case_insensitive(self):
        res = self._login(username='FLOW_QuanLy')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_redirects_to_next(self):
        target = reverse('App_Quanly:products')
        res = self._login(url=f"{reverse('App_Accounts:login')}?next={target}")
        self.assertRedirects(res, target, fetch_redirect_response=False)

    def test_login_ignores_external_next(self):
        res = self._login(url=f"{reverse('App_Accounts:login')}?next=https://evil.example.com/")
        self.assertRedirects(res, reverse('App_Sales:pos'), fetch_redirect_response=False)

    @override_settings(LOGIN_IP_FAILURE_LIMIT=3, LOGIN_FAILURE_LIMIT=10)
    def test_ip_blocked_after_failures_across_usernames(self):
        for idx in range(3):
            self._login(username=f'khong_ton_tai_{idx}', password='sai')
        res = self._login()
        self.assertContains(res, 'nhập sai quá nhiều lần')
        self.assertNotIn('_auth_user_id', self.client.session)
        # IP khác vẫn đăng nhập được.
        self.assertEqual(self._login(ip='10.0.0.2').status_code, 302)

    def test_cleanup_command_removes_expired_counters(self):
        old = timezone.now() - timedelta(days=3)
        LoginAttempt.objects.create(username='cu', ip_address='1.1.1.1', failure_count=2, last_failure_at=old)
        LoginAttempt.objects.create(
            username='dang_khoa', ip_address='1.1.1.1', last_failure_at=timezone.now(),
            locked_until=timezone.now() + timedelta(minutes=5),
        )
        RateLimit.objects.create(scope='login_ip', key='1.1.1.1', count=3, window_started_at=old)
        RateLimit.objects.create(scope='login_ip', key='2.2.2.2', count=1, window_started_at=timezone.now())
        call_command('cleanup_auth_throttle', stdout=StringIO())
        self.assertEqual(list(LoginAttempt.objects.values_list('username', flat=True)), ['dang_khoa'])
        self.assertEqual(list(RateLimit.objects.values_list('key', flat=True)), ['2.2.2.2'])


@override_settings(PASSWORD_RESET_ENABLED=True, LOGIN_TRUST_X_REAL_IP=False)
class PasswordResetTests(TestCase):
    def setUp(self):
        tenant = Tenant.objects.create(name='Reset', public_slug='reset')
        self.user = User.objects.create_user(
            username='reset_quanly', email='chu@example.com', password='Cu@2026abc', tenant=tenant,
            role=User.Role.MANAGER,
        )

    def test_login_page_links_to_password_reset(self):
        html = self.client.get(reverse('App_Accounts:login')).content.decode('utf-8')
        self.assertIn(reverse('App_Accounts:password_reset'), html)

    def test_full_reset_flow(self):
        res = self.client.post(reverse('App_Accounts:password_reset'), {'email': 'CHU@example.com'})
        self.assertRedirects(res, reverse('App_Accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('reset_quanly', body)

        link = re.search(r'https?://[^/]+(/\S+)', body).group(1)
        res = self.client.get(link, follow=True)
        self.assertContains(res, 'Đặt mật khẩu mới')
        res = self.client.post(
            res.redirect_chain[-1][0], {'new_password1': 'Moi@2026xyz', 'new_password2': 'Moi@2026xyz'}
        )
        self.assertRedirects(res, reverse('App_Accounts:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Moi@2026xyz'))

    def test_unknown_email_sends_nothing_but_same_response(self):
        res = self.client.post(reverse('App_Accounts:password_reset'), {'email': 'khong@example.com'})
        self.assertRedirects(res, reverse('App_Accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PASSWORD_RESET_LIMIT_PER_IP=2)
    def test_reset_requests_rate_limited_per_ip(self):
        for _ in range(2):
            self.client.post(reverse('App_Accounts:password_reset'), {'email': 'chu@example.com'})
        res = self.client.post(reverse('App_Accounts:password_reset'), {'email': 'chu@example.com'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'quá nhiều lần')
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(PASSWORD_RESET_ENABLED=False)
    def test_disabled_without_email_config(self):
        # Http404 -> handler404 của dự án chuyển hướng, miễn không hiện form.
        self.assertNotEqual(self.client.get(reverse('App_Accounts:password_reset')).status_code, 200)
        html = self.client.get(reverse('App_Accounts:login')).content.decode('utf-8')
        self.assertNotIn(reverse('App_Accounts:password_reset'), html)

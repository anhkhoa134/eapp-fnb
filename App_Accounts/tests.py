from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
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
            'username': 'gocpho_quanly',
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

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

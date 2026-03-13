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

    def test_manager_can_access_account_profile(self):
        tenant = Tenant.objects.create(name='Demo', public_slug='demo-profile')
        store = Store.objects.create(tenant=tenant, name='Store 1', is_default=True)
        manager = User.objects.create_user(
            username='manager_profile',
            password='123456',
            tenant=tenant,
            role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=manager, store=store, is_default=True)
        self.client.login(username='manager_profile', password='123456')

        res = self.client.get(reverse('App_Accounts:profile'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Thông tin tài khoản quản lý', res.content.decode('utf-8'))

    def test_staff_cannot_access_account_profile(self):
        tenant = Tenant.objects.create(name='Demo', public_slug='demo-profile-staff')
        store = Store.objects.create(tenant=tenant, name='Store 1', is_default=True)
        staff = User.objects.create_user(
            username='staff_profile',
            password='123456',
            tenant=tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=staff, store=store, is_default=True)
        self.client.login(username='staff_profile', password='123456')

        res = self.client.get(reverse('App_Accounts:profile'))
        self.assertEqual(res.status_code, 403)

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Tenant.models import Store, Tenant, UserStoreAccess


class NotFoundRedirectTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant', public_slug='demo-tenant')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.manager = User.objects.create_user(
            username='manager_not_found',
            password='123456',
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        self.staff = User.objects.create_user(
            username='staff_not_found',
            password='123456',
            role=User.Role.STAFF,
            tenant=self.tenant,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)
        self.superuser = User.objects.create_superuser(
            username='super_not_found',
            email='super@example.com',
            password='123456',
        )

    def test_404_redirects_unauthenticated_user_to_login(self):
        response = self.client.get('/khong-ton-tai/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('App_Accounts:login'))

    def test_404_redirects_manager_to_dashboard(self):
        self.client.force_login(self.manager)
        response = self.client.get('/khong-ton-tai/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('App_Quanly:dashboard'))

    def test_404_redirects_staff_to_pos(self):
        self.client.force_login(self.staff)
        response = self.client.get('/khong-ton-tai/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('App_Sales:pos'))

    def test_404_redirects_superuser_to_admin(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/khong-ton-tai/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:index'))

    def test_404_unknown_api_returns_json_payload(self):
        response = self.client.get('/api/khong-ton-tai/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json().get('detail'), 'Đường dẫn không tồn tại.')

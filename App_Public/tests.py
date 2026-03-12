from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Tenant.models import Store, Tenant, UserStoreAccess


class RoutingAndPublicTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.user = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.user, store=self.store, is_default=True)

    def test_root_requires_login(self):
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/accounts/login/', res.url)

    def test_public_slug_route_works(self):
        res = self.client.get(reverse('App_Public:tenant_catalog', kwargs={'public_slug': 'demo'}))
        self.assertEqual(res.status_code, 200)

    def test_root_after_login_renders_pos(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get(reverse('App_Sales:pos'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('id=\"product-container\"', res.content.decode('utf-8'))

    def test_quanly_route_not_captured_by_public_slug(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get('/quanly/')
        self.assertEqual(res.status_code, 403)

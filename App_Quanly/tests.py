from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Tenant.models import Store, Tenant, UserStoreAccess


class QuanlyPermissionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)

        self.manager = User.objects.create_user(
            username='manager_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.MANAGER,
        )
        self.staff = User.objects.create_user(
            username='staff_demo',
            password='123456',
            tenant=self.tenant,
            role=User.Role.STAFF,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        UserStoreAccess.objects.create(user=self.staff, store=self.store, is_default=True)

    def test_manager_can_access_dashboard(self):
        self.client.login(username='manager_demo', password='123456')
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 200)

    def test_staff_cannot_access_dashboard(self):
        self.client.login(username='staff_demo', password='123456')
        res = self.client.get(reverse('App_Quanly:dashboard'))
        self.assertEqual(res.status_code, 403)

    def test_manager_can_access_topping_crud_pages(self):
        self.client.login(username='manager_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:toppings')).status_code, 200)
        self.assertEqual(self.client.get(reverse('App_Quanly:product_toppings')).status_code, 200)

    def test_staff_cannot_access_topping_crud_pages(self):
        self.client.login(username='staff_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:toppings')).status_code, 403)
        self.assertEqual(self.client.get(reverse('App_Quanly:product_toppings')).status_code, 403)

    def test_manager_can_access_staff_management_pages(self):
        self.client.login(username='manager_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:staffs')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id})).status_code,
            200,
        )

    def test_staff_cannot_access_staff_management_pages(self):
        self.client.login(username='staff_demo', password='123456')
        self.assertEqual(self.client.get(reverse('App_Quanly:staffs')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id})).status_code,
            403,
        )

    def test_manager_can_reset_staff_password(self):
        self.client.login(username='manager_demo', password='123456')
        res = self.client.post(
            reverse('App_Quanly:staff_password_reset', kwargs={'pk': self.staff.id}),
            data={
                'new_password1': 'Reset@1234',
                'new_password2': 'Reset@1234',
            },
        )
        self.assertEqual(res.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password('Reset@1234'))

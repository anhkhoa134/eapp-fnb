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


class ResetDemoDataTests(TestCase):
    def test_reset_wipes_user_changes_and_restores_demo_accounts(self):
        from decimal import Decimal
        from io import StringIO

        from django.core.management import call_command
        from django.test import override_settings

        from App_Catalog.models import Product
        from App_Sales.models import Order

        with override_settings(DEMO_SEED_DEFAULT_PASSWORD='123456'):
            call_command('reset_demo_data', stdout=StringIO())
            tenant = Tenant.objects.get(public_slug='demo')
            manager = User.objects.get(username='demo_quanly')
            store = Store.objects.filter(tenant=tenant).first()

            # Người thử demo phá dữ liệu: đổi mật khẩu, thêm tài khoản, sản phẩm, cửa hàng, đơn hàng.
            manager.set_password('bi-doi-mat-khau')
            manager.save()
            User.objects.create_user(username='nguoi_la', password='x', tenant=tenant)
            Product.objects.create(tenant=tenant, name='Món lạ')
            Store.objects.create(tenant=tenant, name='CN Lạ')
            Order.objects.create(
                tenant=tenant, store=store, cashier=manager, payment_method=Order.PaymentMethod.CASH,
                status=Order.Status.COMPLETED, subtotal=Decimal('1000'), tax_rate=Decimal('0'),
                tax_amount=Decimal('0'), total_amount=Decimal('1000'), customer_paid=Decimal('1000'),
                change_amount=Decimal('0'),
            )

            call_command('reset_demo_data', stdout=StringIO())

        tenant = Tenant.objects.get(public_slug='demo')
        self.assertTrue(User.objects.get(username='demo_quanly').check_password('123456'))
        self.assertTrue(User.objects.filter(username='demo_nhanvien_1', tenant=tenant).exists())
        self.assertFalse(User.objects.filter(username='nguoi_la').exists())
        self.assertFalse(Product.objects.filter(name='Món lạ').exists())
        self.assertFalse(Store.objects.filter(name='CN Lạ').exists())
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Tenant.objects.filter(public_slug='demo').count(), 1)

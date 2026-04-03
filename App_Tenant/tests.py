from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable
from App_Tenant.admin import StoreAdmin, StoreAdminForm, TenantAdmin, TenantAdminForm
from App_Tenant.models import Store, Tenant, UserStoreAccess


class TenantModelTests(TestCase):
    def test_reserved_public_slug_invalid(self):
        tenant = Tenant(name='Tenant 1', public_slug='quanly')
        with self.assertRaises(ValidationError):
            tenant.full_clean()

    def test_unique_manager_per_tenant(self):
        tenant = Tenant.objects.create(name='Tenant A', public_slug='tenant-a')
        User.objects.create_user(username='manager_1', password='123456', role=User.Role.MANAGER, tenant=tenant)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username='manager_2',
                    password='123456',
                    role=User.Role.MANAGER,
                    tenant=tenant,
                )

    def test_user_store_access_same_tenant_required(self):
        tenant_1 = Tenant.objects.create(name='Tenant 1', public_slug='tenant-1')
        tenant_2 = Tenant.objects.create(name='Tenant 2', public_slug='tenant-2')
        user = User.objects.create_user(username='staff_a', password='123456', role=User.Role.STAFF, tenant=tenant_1)
        store_other = Store.objects.create(tenant=tenant_2, name='Store other', is_default=True)

        link = UserStoreAccess(user=user, store=store_other, is_default=True)
        with self.assertRaises(ValidationError):
            link.full_clean()


class TenantAdminPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.model_admin = TenantAdmin(Tenant, AdminSite())

    def test_superuser_can_add_tenant_in_admin(self):
        request = self.factory.get('/')
        request.user = User.objects.create_superuser(
            username='super_admin_tenant',
            email='super_admin_tenant@example.com',
            password='123456',
        )
        self.assertTrue(self.model_admin.has_add_permission(request))

    def test_non_superuser_cannot_add_tenant_in_admin(self):
        tenant = Tenant.objects.create(name='Demo', public_slug='demo')
        request = self.factory.get('/')
        request.user = User.objects.create_user(
            username='manager_admin_tenant',
            password='123456',
            role=User.Role.MANAGER,
            tenant=tenant,
        )
        self.assertFalse(self.model_admin.has_add_permission(request))

    def test_tenant_and_store_slug_autofill_configured(self):
        store_admin = StoreAdmin(Store, AdminSite())
        self.assertEqual(self.model_admin.prepopulated_fields, {'public_slug': ('name',)})
        self.assertEqual(store_admin.prepopulated_fields, {'slug': ('name',)})

    def test_tenant_form_blank_public_slug_auto_generates_unique_value(self):
        Tenant.objects.create(name='Demo Tenant', public_slug='demo-tenant')
        form = TenantAdminForm(
            data={
                'name': 'Demo Tenant',
                'public_slug': '',
                'is_active': True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['public_slug'], 'demo-tenant-2')
        self.assertFalse(form.fields['public_slug'].required)
        self.assertIn('Để trống', form.fields['public_slug'].help_text)

    def test_store_form_blank_slug_auto_generates_unique_value(self):
        tenant = Tenant.objects.create(name='Store Tenant', public_slug='store-tenant')
        Store.objects.create(tenant=tenant, name='Cửa hàng trung tâm', is_active=True, is_default=True)
        form = StoreAdminForm(
            data={
                'tenant': tenant.id,
                'name': 'Cửa hàng trung tâm',
                'slug': '',
                'address': '',
                'is_active': True,
                'is_default': False,
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['slug'], 'cua-hang-trung-tam-2')
        self.assertFalse(form.fields['slug'].required)
        self.assertIn('Để trống', form.fields['slug'].help_text)


class TenantAdminBootstrapDataTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.model_admin = TenantAdmin(Tenant, AdminSite())
        self.superuser = User.objects.create_superuser(
            username='super_admin_bootstrap',
            email='super_admin_bootstrap@example.com',
            password='123456',
        )

    def test_create_tenant_in_admin_bootstraps_default_data(self):
        request = self.factory.post('/admin/App_Tenant/tenant/add/')
        request.user = self.superuser
        tenant = Tenant(name='Tenant Bootstrap', public_slug='tenant-bootstrap')

        self.model_admin.save_model(request, tenant, form=None, change=False)

        self.assertEqual(Store.objects.filter(tenant=tenant).count(), 1)
        store = Store.objects.get(tenant=tenant)
        self.assertTrue(store.is_default)

        self.assertEqual(User.objects.filter(tenant=tenant, role=User.Role.MANAGER).count(), 1)
        self.assertEqual(User.objects.filter(tenant=tenant, role=User.Role.STAFF).count(), 2)
        self.assertEqual(UserStoreAccess.objects.filter(store=store).count(), 3)
        self.assertEqual(UserStoreAccess.objects.filter(store=store, is_default=True).count(), 3)

        self.assertEqual(DiningTable.objects.filter(tenant=tenant, store=store).count(), 12)
        self.assertEqual(DiningTable.objects.filter(tenant=tenant, store=store, qr_token='').count(), 0)

        self.assertEqual(Category.objects.filter(tenant=tenant).count(), 2)
        self.assertEqual(StoreCategory.objects.filter(store=store, is_visible=True).count(), 2)

        self.assertEqual(Product.objects.filter(tenant=tenant, is_active=True).count(), 4)
        self.assertEqual(ProductUnit.objects.filter(product__tenant=tenant, is_active=True).count(), 4)
        self.assertEqual(StoreProduct.objects.filter(store=store, is_available=True).count(), 4)

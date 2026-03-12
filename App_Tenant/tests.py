from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from App_Accounts.models import User
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

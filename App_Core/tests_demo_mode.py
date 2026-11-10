"""Site công khai có tenant demo (DEMO_MODE=1): khách dùng thử không khoá được tài khoản demo dùng chung."""
import os
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from App_Accounts.models import User
from App_Tenant.models import Tenant

PASSWORD = '123456'
NEW_PASSWORD = 'DemoFnB!558123'


@override_settings(DEMO_MODE=True, DEMO_SEED_DEFAULT_PASSWORD=PASSWORD)
class SharedDemoAccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('reset_demo_data', stdout=StringIO())
        cls.tenant = Tenant.objects.get(public_slug='demo')
        cls.manager = User.objects.get(username='demo_quanly')
        cls.staff = User.objects.get(username='demo_nhanvien_1')

    def test_login_page_shows_demo_accounts_only_in_demo_mode(self):
        self.assertContains(self.client.get(reverse('App_Accounts:login')), 'id="demo-accounts"')
        with override_settings(DEMO_MODE=False):
            self.assertNotContains(self.client.get(reverse('App_Accounts:login')), 'id="demo-accounts"')

    def test_manager_cannot_change_own_password_or_email(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Accounts:password_change'), {
            'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.client.post(reverse('App_Quanly:account'), {
            'form_action': 'password_change',
            'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.client.post(reverse('App_Quanly:account'), {
            'form_action': 'profile', 'first_name': 'Khách', 'email': 'khach@example.com', 'tenant_name': 'Demo FNB',
        })
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.check_password(PASSWORD))
        self.assertEqual(self.manager.email, 'demo_quanly@demo.local')

    def test_manager_can_still_rename_self(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:account'), {
            'form_action': 'profile', 'first_name': 'Khách', 'email': 'demo_quanly@demo.local', 'tenant_name': 'Demo FNB',
        })
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.first_name, 'Khách')

    def test_manager_cannot_lock_or_change_shared_staff(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:staff_edit', args=[self.staff.pk]), {'role': 'staff', 'is_active': ''})
        self.client.post(reverse('App_Quanly:staff_password_reset', args=[self.staff.pk]), {
            'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.client.post(reverse('App_Quanly:staff_delete', args=[self.staff.pk]))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)
        self.assertTrue(self.staff.check_password(PASSWORD))

    def test_manager_still_manages_staff_they_created(self):
        visitor_staff = User.objects.create_user(
            username='khach_tao', password=PASSWORD, tenant=self.tenant, role=User.Role.STAFF,
        )
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:staff_delete', args=[visitor_staff.pk]))
        self.assertFalse(User.objects.filter(pk=visitor_staff.pk).exists())

    def test_password_reset_sends_nothing_for_demo_account(self):
        User.objects.filter(pk=self.manager.pk).update(email='khach@example.com')
        response = self.client.post(reverse('App_Accounts:password_reset'), {'email': 'khach@example.com'})
        self.assertRedirects(response, reverse('App_Accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(DEMO_MODE=False)
    def test_without_demo_mode_demo_accounts_behave_normally(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Accounts:password_change'), {
            'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.check_password(NEW_PASSWORD))


class ResetDemoCommandGuardTests(TestCase):
    def test_refused_in_prod_without_allow_demo_seed(self):
        with override_settings(ENVIRONMENT='prod'), patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ALLOW_DEMO_SEED', None)
            for command in ('reset_demo_data', 'seed_initial_data'):
                with self.subTest(command=command), self.assertRaises(CommandError):
                    call_command(command, stdout=StringIO())
        self.assertFalse(Tenant.objects.filter(public_slug='demo').exists())

    def test_allowed_in_prod_with_allow_demo_seed(self):
        with override_settings(ENVIRONMENT='prod'), patch.dict(os.environ, {'ALLOW_DEMO_SEED': '1'}):
            call_command('reset_demo_data', stdout=StringIO())
        self.assertTrue(Tenant.objects.filter(public_slug='demo').exists())

    def test_older_than_days_skips_recent_reset(self):
        call_command('reset_demo_data', stdout=StringIO())
        manager = User.objects.get(username='demo_quanly')
        manager.set_password('bi-doi')
        manager.save()
        call_command('reset_demo_data', '--older-than-days', '2.5', stdout=StringIO())
        manager.refresh_from_db()
        self.assertTrue(manager.check_password('bi-doi'))

"""Email tài khoản giao diện eApp ERP (quên mật khẩu, kích hoạt đăng ký) và cờ seed --demo/--superadmin."""
import os
import re
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from App_Accounts.models import User

SIGNUP = {
    'store_name': 'Quán Thử Email', 'username': 'quan_thu_email', 'email': 'chu.quan@example.com',
    'password1': 'MatKhau!2468', 'password2': 'MatKhau!2468',
}


def _link(message):
    return re.search(r'https?://\S+', message.body).group(0)


@override_settings(PASSWORD_RESET_ENABLED=True, SIGNUP_REQUIRE_EMAIL_VERIFICATION=True)
class AccountEmailTests(TestCase):
    def test_password_reset_email_uses_erp_layout_and_link_works(self):
        user = User.objects.create_user('khach', email='khach@example.com', password='Cu!12345678')
        self.client.post(reverse('App_Accounts:password_reset'), {'email': 'khach@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, 'Đặt lại mật khẩu eApp FnB')
        html = message.alternatives[0][0]
        for text in ('Khôi phục mật khẩu', 'Đặt lại mật khẩu ngay', 'Hết hạn sau 2 giờ', 'eApp FnB —', 'khach'):
            self.assertIn(text, html)
        response = self.client.get(_link(message), follow=True)
        response = self.client.post(response.redirect_chain[-1][0], {
            'new_password1': 'Moi!98765432', 'new_password2': 'Moi!98765432',
        })
        user.refresh_from_db()
        self.assertTrue(user.check_password('Moi!98765432'))

    def test_signup_requires_activation_email(self):
        response = self.client.post(reverse('App_Accounts:signup'), SIGNUP)
        self.assertRedirects(response, reverse('App_Accounts:signup_sent'))
        user = User.objects.get(email='chu.quan@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, 'Kích hoạt tài khoản eApp FnB')
        self.assertIn('Kích hoạt tài khoản ngay', message.alternatives[0][0])

        response = self.client.get(_link(message))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(self.client.get(_link(message)).status_code, 200)  # bấm lại: "đã kích hoạt"

    def test_resend_and_bad_token(self):
        self.client.post(reverse('App_Accounts:signup'), SIGNUP)
        self.client.post(reverse('App_Accounts:signup_resend'), {'email': 'chu.quan@example.com'})
        self.assertEqual(len(mail.outbox), 2)
        self.client.post(reverse('App_Accounts:signup_resend'), {'email': 'khong-co@example.com'})
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.get(reverse('App_Accounts:signup_verify', args=['sai-token']))
        self.assertEqual(response.status_code, 400)

    @override_settings(SIGNUP_REQUIRE_EMAIL_VERIFICATION=False)
    def test_signup_without_verification_logs_in_directly(self):
        self.client.post(reverse('App_Accounts:signup'), SIGNUP)
        self.assertTrue(User.objects.get(email='chu.quan@example.com').is_active)
        self.assertEqual(len(mail.outbox), 0)


class SeedAccountFlagTests(TestCase):
    def test_superadmin_only_creates_superuser_not_demo(self):
        call_command('seed_initial_data', '--superadmin', stdout=StringIO())
        admin = User.objects.get(username='superadmin')
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertFalse(User.objects.filter(username='demo_quanly').exists())

    def test_demo_flag_never_creates_staff(self):
        call_command('seed_initial_data', '--demo', stdout=StringIO())
        self.assertFalse(User.objects.filter(username__startswith='demo_', is_staff=True).exists())
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    def test_prod_superadmin_needs_strong_password_but_not_allow_demo_seed(self):
        with override_settings(ENVIRONMENT='prod'), patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ALLOW_DEMO_SEED', None)
            os.environ.pop('SUPERADMIN_PASSWORD', None)
            with self.assertRaises(CommandError):
                call_command('seed_initial_data', '--superadmin', stdout=StringIO())
            with self.assertRaises(CommandError):
                call_command('seed_initial_data', '--superadmin', '--superadmin-password', '123456', stdout=StringIO())
            call_command('seed_initial_data', '--superadmin', '--superadmin-password', 'Chu-Site!Manh-2026', stdout=StringIO())
            with self.assertRaises(CommandError):
                call_command('seed_initial_data', '--demo', stdout=StringIO())
        self.assertTrue(User.objects.get(username='superadmin').check_password('Chu-Site!Manh-2026'))

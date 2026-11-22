"""Đăng nhập khi tài khoản tự đăng ký chưa bấm link kích hoạt trong email."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

User = get_user_model()
LOGIN_URL = 'App_Accounts:login'
RESEND_URL = 'App_Accounts:signup_resend'
PASSWORD = 'MatKhau!2468'


class LoginBeforeActivationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cho_kich_hoat', email='cho@example.com', password=PASSWORD, is_active=False,
        )

    def _login(self, password):
        return self.client.post(reverse(LOGIN_URL), {'username': 'cho_kich_hoat', 'password': password}, follow=True)

    def test_correct_password_says_not_activated_with_resend_link(self):
        response = self._login(PASSWORD)
        self.assertContains(response, 'Tài khoản chưa được kích hoạt')
        self.assertContains(response, reverse(RESEND_URL))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session['signup_email'], 'cho@example.com')

    def test_wrong_password_keeps_generic_error(self):
        response = self._login('Sai!13579')
        self.assertNotContains(response, 'chưa được kích hoạt')
        self.assertNotIn('signup_email', self.client.session)

    def test_disabled_account_keeps_generic_error(self):
        self.user.last_login = timezone.now()
        self.user.save(update_fields=['last_login'])
        response = self._login(PASSWORD)
        self.assertNotContains(response, 'chưa được kích hoạt')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_activated_account_logs_in(self):
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        self._login(PASSWORD)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

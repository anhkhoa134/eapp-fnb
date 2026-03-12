from django.test import TestCase
from django.urls import reverse


class AccountUiTests(TestCase):
    def test_login_page_contains_base_containers(self):
        res = self.client.get(reverse('App_Accounts:login'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('id="spinnerContainer"', html)
        self.assertIn('id="toastContainer"', html)
        self.assertIn('id="commonModal"', html)

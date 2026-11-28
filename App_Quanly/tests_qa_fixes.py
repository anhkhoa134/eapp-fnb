"""Kiểm thử lỗi QA fnb.eapp.vn 20–28/11/2026: tiêu đề trang quản lý và noindex trang nội bộ (FNB-09)."""
from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Tenant.models import Store, Tenant, UserStoreAccess


class QaFixTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo QA', public_slug='demo-qa')
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.manager = User.objects.create_user(
            username='manager_qa', password='123456', tenant=self.tenant, role=User.Role.MANAGER,
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)

    def test_quanly_pages_have_their_own_title_and_noindex(self):
        self.client.force_login(self.manager)
        for name, title in (
            ('dashboard', 'Tổng quan'),
            ('orders', 'Lịch sử đơn'),
            ('products', 'Sản phẩm'),
            ('qr_tables', 'QR bàn'),
        ):
            response = self.client.get(reverse(f'App_Quanly:{name}'))
            self.assertContains(response, f'<title>{title} | eApp FnB</title>', msg_prefix=name)
            self.assertContains(response, '<meta name="robots" content="noindex, nofollow">', msg_prefix=name)

    def test_pos_page_is_noindex(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('App_Sales:pos'))
        self.assertContains(response, '<title>Bán hàng | eApp FnB</title>')
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

    def test_login_page_stays_indexable(self):
        response = self.client.get(reverse('App_Accounts:login'))
        self.assertNotContains(response, 'noindex')

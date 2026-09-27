from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit
from App_Sales.models import Customer
from App_Tenant.models import Store, Tenant, UserStoreAccess


class DuplicateGuardTests(TestCase):
    """BL-034: dữ liệu trùng ràng buộc unique phải báo lỗi form, không 500."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Dup', public_slug='dup')
        store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.manager = User.objects.create_user(
            username='dup_manager', password='123456', tenant=self.tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.manager, store=store, is_default=True)
        self.client.force_login(self.manager)
        self.customer_a = Customer.objects.create(tenant=self.tenant, name='Khách A', phone='0901234567')
        self.customer_b = Customer.objects.create(tenant=self.tenant, name='Khách B', phone='0907654321')

    def _customer_payload(self, name, phone):
        return {'name': name, 'phone': phone, 'email': '', 'note': '', 'is_active': 'on'}

    def test_create_customer_with_duplicate_phone_shows_form_error(self):
        res = self.client.post(reverse('App_Quanly:customers'), self._customer_payload('Khách C', ' 0901234567 '))
        self.assertEqual(res.status_code, 200)
        self.assertIn('phone', res.context['form'].errors)
        self.assertContains(res, 'Số điện thoại đã thuộc khách hàng')
        self.assertEqual(Customer.objects.filter(tenant=self.tenant).count(), 2)

    def test_create_customer_same_phone_other_tenant_ok(self):
        other = Tenant.objects.create(name='Other', public_slug='other')
        Customer.objects.create(tenant=other, name='Khách X', phone='0911111111')
        res = self.client.post(reverse('App_Quanly:customers'), self._customer_payload('Khách C', '0911111111'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Customer.objects.filter(tenant=self.tenant, phone='0911111111').exists())

    def test_edit_customer_to_duplicate_phone_is_rejected(self):
        res = self.client.post(
            reverse('App_Quanly:customer_edit', args=[self.customer_b.pk]),
            self._customer_payload('Khách B', '0901234567'),
        )
        self.assertEqual(res.status_code, 302)
        self.customer_b.refresh_from_db()
        self.assertEqual(self.customer_b.phone, '0907654321')

    def test_edit_customer_keeping_own_phone_ok(self):
        res = self.client.post(
            reverse('App_Quanly:customer_edit', args=[self.customer_a.pk]),
            self._customer_payload('Khách A mới', '0901234567'),
        )
        self.assertEqual(res.status_code, 302)
        self.customer_a.refresh_from_db()
        self.assertEqual(self.customer_a.name, 'Khách A mới')

    def test_duplicate_product_unit_name_does_not_500(self):
        category = Category.objects.create(tenant=self.tenant, name='Nước')
        product = Product.objects.create(tenant=self.tenant, category=category, name='Trà')
        ProductUnit.objects.create(product=product, name='M', price=Decimal('30000'))
        unit_l = ProductUnit.objects.create(product=product, name='L', price=Decimal('35000'))

        res = self.client.post(
            reverse('App_Quanly:unit_add', args=[product.pk]),
            {'name': 'M', 'price': '32000', 'sku': '', 'is_active': 'on'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(product.units.count(), 2)

        res = self.client.post(
            reverse('App_Quanly:unit_edit', args=[unit_l.pk]),
            {'name': 'M', 'price': '35000', 'sku': '', 'is_active': 'on'},
        )
        self.assertEqual(res.status_code, 302)
        unit_l.refresh_from_db()
        self.assertEqual(unit_l.name, 'L')

        res = self.client.post(
            reverse('App_Quanly:unit_edit', args=[unit_l.pk]),
            {'name': 'L', 'price': '36000', 'sku': '', 'is_active': 'on'},
        )
        unit_l.refresh_from_db()
        self.assertEqual(unit_l.price, Decimal('36000'))

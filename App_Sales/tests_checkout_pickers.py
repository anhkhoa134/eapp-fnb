from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import User
from App_Sales.models import Customer, Order, Promotion
from App_Tenant.models import Store, Tenant, UserStoreAccess


class CheckoutPickerTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Pickers', public_slug='pickers')
        self.other = Tenant.objects.create(name='Other', public_slug='other-picker')
        self.store = Store.objects.create(tenant=self.tenant, name='Store', is_default=True)
        self.user = User.objects.create_user(username='picker', tenant=self.tenant, role=User.Role.STAFF)
        UserStoreAccess.objects.create(user=self.user, store=self.store, is_default=True)
        self.client.force_login(self.user)
        self.url = reverse('App_Sales_API:promotions')

    def promo(self, **kwargs):
        values = dict(tenant=self.tenant, name='Giảm giá', code='SALE10',
                      discount_type=Promotion.DiscountType.PERCENT, discount_value=Decimal('10'))
        values.update(kwargs)
        return Promotion.objects.create(**values)

    def fetch(self, **kwargs):
        return self.client.get(self.url, {'store_id': self.store.pk, 'subtotal': 100000, **kwargs})

    def test_code_normalization_uniqueness_and_legacy_blank_codes(self):
        p = self.promo(code=' sale10 ')
        self.assertEqual(p.code, 'SALE10')
        with self.assertRaises(ValidationError):
            self.promo(code='sale10')
        self.promo(tenant=self.other)
        self.promo(code='')
        self.promo(code='')
        self.assertEqual(self.fetch(code='sale10').json()['promotions'][0]['id'], p.pk)

    def test_search_and_code_validation_respect_eligibility_and_tenant(self):
        self.promo(code='VALID', name='Happy hour')
        self.promo(code='FOREIGN', tenant=self.other)
        self.promo(code='EXPIRED', valid_to=timezone.now()-timedelta(days=1))
        self.promo(code='MINIMUM', min_order_amount=200000)
        self.promo(code='INACTIVE', is_active=False)
        restricted = self.promo(code='STORE')
        restricted.stores.add(Store.objects.create(tenant=self.tenant, name='Other store'))
        self.assertEqual([p['code'] for p in self.fetch(q='Happy').json()['promotions']], ['VALID'])
        for code in ('FOREIGN', 'EXPIRED', 'MINIMUM', 'INACTIVE', 'STORE', 'UNKNOWN'):
            with self.subTest(code=code):
                self.assertEqual(self.fetch(code=code).status_code, 400)
        self.assertEqual(self.fetch(promotion_id='not-an-id').status_code, 400)
        self.assertEqual(self.fetch(subtotal='NaN').status_code, 400)

    def test_recent_promotions_prioritize_last_use_and_limit_results(self):
        recent = self.promo(code='USED')
        for i in range(32):
            self.promo(code=f'NEW{i}')
        Order.objects.create(tenant=self.tenant, store=self.store, cashier=self.user, promotion=recent,
                             payment_method='cash', subtotal=100000, tax_amount=0, total_amount=90000, customer_paid=90000)
        rows = self.fetch().json()['promotions']
        self.assertEqual(len(rows), 30)
        self.assertEqual(rows[0]['code'], 'USED')

    def test_recent_customers_search_and_feature_flags(self):
        used = Customer.objects.create(tenant=self.tenant, name='Khách cũ', phone='0901234567', last_order_at=timezone.now())
        Customer.objects.create(tenant=self.tenant, name='Mới', phone='0901234568')
        Customer.objects.create(tenant=self.other, name='Other', phone='0901234569')
        Customer.objects.create(tenant=self.tenant, name='Inactive', phone='0901234570', is_active=False)
        url = reverse('App_Sales_API:customers')
        rows = self.client.get(url).json()['customers']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['id'], used.pk)
        self.assertEqual(self.client.get(url, {'q': 'khach cu'}).json()['customers'][0]['id'], used.pk)
        self.tenant.show_customer_feature = False
        self.tenant.show_promotion_feature = False
        self.tenant.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.fetch().status_code, 403)

    def test_manager_create_code_and_duplicate_form_error(self):
        self.user.role = User.Role.MANAGER
        self.user.save()
        url = reverse('App_Quanly:promotions')
        payload = {'name': 'Giảm mới', 'code': ' new10 ', 'discount_type': 'percent',
                   'discount_value': '10', 'min_order_amount': '0', 'is_active': 'on'}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Promotion.objects.filter(tenant=self.tenant, code='NEW10').exists())
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mã khuyến mãi đã tồn tại')
        self.assertEqual(Promotion.objects.filter(tenant=self.tenant, code='NEW10').count(), 1)
        self.assertContains(self.client.get(url, {'q': 'new10'}), 'Giảm mới')

    def quick_create(self, **values):
        payload = {'name': 'Ưu đãi nhanh', 'code': ' quick10 ', 'discount_type': 'percent',
                   'discount_value': '10', 'min_order_amount': '0', 'store_id': self.store.pk, **values}
        return self.client.post(reverse('App_Sales_API:promotions_quick_add'), payload, content_type='application/json')

    def test_quick_create_requires_manager_and_enabled_feature(self):
        self.assertEqual(self.quick_create().status_code, 403)
        self.user.role = User.Role.MANAGER
        self.user.save()
        self.tenant.show_promotion_feature = False
        self.tenant.save()
        self.assertEqual(self.quick_create().status_code, 403)
        self.assertFalse(Promotion.objects.exists())

    def test_quick_create_scopes_to_current_store_and_rejects_duplicates(self):
        self.user.role = User.Role.MANAGER
        self.user.save()
        result = self.quick_create(tenant_id=self.other.pk)
        self.assertEqual(result.status_code, 201, result.content)
        p = Promotion.objects.get(code='QUICK10')
        self.assertEqual(p.tenant_id, self.tenant.pk)
        self.assertEqual(list(p.stores.values_list('pk', flat=True)), [self.store.pk])
        self.assertEqual(self.fetch(code='quick10').json()['promotions'][0]['id'], p.pk)
        self.assertEqual(self.quick_create().status_code, 400)
        self.assertEqual(Promotion.objects.count(), 1)
        self.assertEqual(self.quick_create(code='FIXED', discount_type='amount', discount_value='5000').status_code, 201)
        self.assertEqual(Promotion.objects.get(code='FIXED').discount_type, Promotion.DiscountType.FIXED)

    def test_quick_create_validation_and_foreign_store(self):
        self.user.role = User.Role.MANAGER
        self.user.save()
        other_store = Store.objects.create(tenant=self.other, name='Foreign')
        self.assertEqual(self.quick_create(store_id=other_store.pk).status_code, 403)
        for values in ({'code': ''}, {'name': ''}, {'discount_value': '101'}, {'discount_value': 'NaN'},
                       {'discount_value': '-1'}, {'discount_value': 'abc'}, {'min_order_amount': '-1'},
                       {'max_discount_amount': '-1'}, {'code': ['bad']}, {'store_id': {}}, {'store_id': 'x'}):
            with self.subTest(values=values):
                self.assertEqual(self.quick_create(**values).status_code, 400)
        self.assertFalse(Promotion.objects.exists())

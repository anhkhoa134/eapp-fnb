"""Hồi quy cho báo cáo kiểm thử fnb.eapp.vn 29/10/2026 (validation dữ liệu ở trang quản lý)."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, Topping
from App_Quanly.forms import CustomerForm, DiningTableForm, ProductForm, PromotionForm
from App_Sales.models import Customer, DiningTable, Shift
from App_Tenant.models import Store, Tenant, UserStoreAccess


class QaReportBase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo QA', public_slug='demo-qa', show_shift_feature=True)
        self.store = Store.objects.create(tenant=self.tenant, name='CN Trung Tâm', is_default=True)
        self.manager = User.objects.create_user(
            username='qa_manager', password='123456', tenant=self.tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        self.client.force_login(self.manager)
        self.product = Product.objects.create(tenant=self.tenant, name='Cà phê')


class PriceValidationTests(QaReportBase):
    """BUG-01: giá âm bị đổi dấu, 0đ và 99.999.999.999đ được chấp nhận."""

    def add_unit(self, price):
        return self.client.post(reverse('App_Quanly:unit_add', args=[self.product.id]), {'name': 'Ly', 'price': price})

    def test_negative_zero_and_huge_unit_price_rejected(self):
        for price, error in (('-5000', 'không được âm'), ('0', 'phải lớn hơn 0'), ('99999999999', 'tối đa')):
            response = self.add_unit(price)
            self.assertFalse(ProductUnit.objects.filter(product=self.product).exists(), price)
            messages = [str(m) for m in response.wsgi_request._messages]
            self.assertTrue(any(error in m for m in messages), (price, messages))

    def test_valid_unit_price_saved(self):
        self.add_unit('35.000')
        self.assertEqual(ProductUnit.objects.get(product=self.product).price, Decimal('35000'))

    def test_negative_topping_price_rejected(self):
        self.tenant.show_topping_feature = True
        self.tenant.save()
        self.client.post(
            reverse('App_Quanly:toppings'),
            {'form_type': 'topping', 'topping-name': 'QA', 'topping-price': '-3000', 'topping-is_active': 'on'},
        )
        self.assertFalse(Topping.objects.filter(tenant=self.tenant).exists())


class ShiftCashValidationTests(QaReportBase):
    """BUG-08: tiền đầu ca "abc" thành 0đ, tiền đếm "-500" thành "Thừa 500 đ"."""

    def test_letters_and_negative_cash_rejected(self):
        url = reverse('App_Sales:shifts')
        self.client.post(url, {'action': 'open', 'store_id': self.store.id, 'opening_cash': 'abc'})
        self.assertFalse(Shift.objects.exists())

        self.client.post(url, {'action': 'open', 'store_id': self.store.id, 'opening_cash': '200.000'})
        shift = Shift.objects.get()
        response = self.client.post(url, {'action': 'close', 'store_id': self.store.id, 'counted_cash': '-500'}, follow=True)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.OPEN)
        self.assertContains(response, 'không được âm')


class CategoryAndTableTests(QaReportBase):
    def test_duplicate_category_name_rejected_case_insensitive(self):
        """BUG-06."""
        Category.objects.create(tenant=self.tenant, name='Đồ uống')
        self.client.post(reverse('App_Quanly:categories'), {'name': 'đồ uống', 'is_active': 'on'})
        self.assertEqual(Category.objects.filter(tenant=self.tenant).count(), 1)

    def test_duplicate_table_code_error_on_code_field_in_vietnamese(self):
        """BUG-04: "Dining table với thông tin Store và Code đã tồn tại"."""
        DiningTable.objects.create(tenant=self.tenant, store=self.store, code='QA-01', name='Bàn 1')
        form = DiningTableForm({'store': self.store.id, 'code': 'qa-01', 'name': 'Bàn 2', 'is_active': 'on'}, tenant=self.tenant)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['code'], ['Mã bàn "QA-01" đã tồn tại ở CN Trung Tâm.'])
        self.assertNotIn('__all__', form.errors)

    def test_blank_table_code_generated_with_store_prefix(self):
        """BUG-14: mã bàn "CN--01" thiếu mã cửa hàng."""
        DiningTable.objects.create(tenant=self.tenant, store=self.store, code='TT-01', name='Bàn 1')
        form = DiningTableForm({'store': self.store.id, 'code': '', 'name': 'Bàn 2', 'is_active': 'on'}, tenant=self.tenant)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['code'], 'TT-02')
        self.assertEqual(Store(name='CN Thủ Đức').table_code_prefix, 'TD')


class CustomerPhoneTests(QaReportBase):
    """BUG-09: SĐT trùng hiện 2 lỗi, SĐT có chữ không nói rõ."""

    def test_duplicate_phone_shows_single_error(self):
        Customer.objects.create(tenant=self.tenant, name='Khách A', phone='0900000001')
        form = CustomerForm({'name': 'Khách B', 'phone': '0900000001', 'is_active': 'on'}, tenant=self.tenant)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['phone'], ['Số điện thoại đã thuộc khách hàng "Khách A".'])

    def test_phone_with_letters_explains_digits_only(self):
        form = CustomerForm({'name': 'Khách', 'phone': 'abc123xyz', 'is_active': 'on'}, tenant=self.tenant)
        self.assertFalse(form.is_valid())
        self.assertIn('chỉ gồm chữ số', form.errors['phone'][0])


class PromotionInvalidInputTests(QaReportBase):
    """BUG-10: giá trị giảm "abc" làm trang lỗi (modal đóng, không thông báo)."""

    def test_letters_in_discount_value_shows_field_error_not_500(self):
        self.tenant.show_promotion_feature = True
        self.tenant.save()
        response = self.client.post(
            reverse('App_Quanly:promotions'),
            {'name': 'KM', 'discount_type': 'fixed', 'discount_value': 'abc', 'min_order_amount': '100.000', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['open_create_modal'])
        self.assertIn('discount_value', response.context['form'].errors)
        self.assertNotIn('min_order_amount', response.context['form'].errors)


class FormLabelTests(QaReportBase):
    def test_select_blank_label_is_vietnamese(self):
        """Mục 11: option "---------" mặc định của Django."""
        self.assertEqual(ProductForm(tenant=self.tenant).fields['category'].empty_label, '— Chọn danh mục —')
        self.assertEqual(DiningTableForm(tenant=self.tenant).fields['store'].empty_label, '— Chọn cửa hàng —')
        promo_choices = dict(PromotionForm(tenant=self.tenant).fields['discount_type'].choices)
        self.assertNotIn('---------', promo_choices.values())

    def test_product_without_store_warns_not_on_pos(self):
        """BUG-07: món không gán cửa hàng / đơn vị không hiện ở POS mà không cảnh báo."""
        response = self.client.post(reverse('App_Quanly:products'), {'name': 'Món A', 'is_active': 'on'}, follow=True)
        self.assertContains(response, 'chưa hiện ở POS')
        self.assertContains(response, 'Chưa hiện ở POS / menu QR')


class TableAreaTests(QaReportBase):
    def test_area_saved_and_returned_by_pos_api(self):
        form = DiningTableForm(
            {'store': self.store.id, 'area': '  Tầng   1 ', 'code': 'T1-01', 'name': 'Bàn 1', 'is_active': 'on'},
            tenant=self.tenant,
        )
        self.assertTrue(form.is_valid(), form.errors)
        table = form.save(commit=False)
        table.tenant = self.tenant
        table.save()
        self.assertEqual(table.area, 'Tầng 1')
        payload = self.client.get(reverse('App_Sales_API:tables'), {'store_id': self.store.id}).json()
        self.assertEqual(payload['tables'][0]['area'], 'Tầng 1')

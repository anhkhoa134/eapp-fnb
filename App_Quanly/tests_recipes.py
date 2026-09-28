from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from App_Accounts.models import User
from App_Catalog.models import Category, Ingredient, Product, ProductUnit, RecipeItem, Topping
from App_Catalog.recipes import compute_ingredient_usage, save_recipe
from App_Sales.models import Order, OrderItem, OrderItemTopping
from App_Tenant.models import Store, SubscriptionPlan, Tenant, UserStoreAccess


class RecipeTestBase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo', public_slug='demo-recipe', show_recipe_feature=True)
        self.store = Store.objects.create(tenant=self.tenant, name='Store 1', is_default=True)
        self.manager = User.objects.create_user(
            username='recipe_manager', password='123456', tenant=self.tenant, role=User.Role.MANAGER
        )
        UserStoreAccess.objects.create(user=self.manager, store=self.store, is_default=True)
        self.staff = User.objects.create_user(
            username='recipe_staff', password='123456', tenant=self.tenant, role=User.Role.STAFF
        )

        category = Category.objects.create(tenant=self.tenant, name='Đồ uống')
        self.product = Product.objects.create(tenant=self.tenant, category=category, name='Cà phê sữa')
        self.unit_m = ProductUnit.objects.create(product=self.product, name='Size M', price=Decimal('25000'))
        self.unit_l = ProductUnit.objects.create(product=self.product, name='Size L', price=Decimal('30000'))
        self.topping = Topping.objects.create(tenant=self.tenant, name='Trân châu', price=Decimal('5000'))

        self.coffee = Ingredient.objects.create(
            tenant=self.tenant, name='Cà phê hạt', unit='g', cost_per_unit=Decimal('350')
        )
        self.milk = Ingredient.objects.create(
            tenant=self.tenant, name='Sữa đặc', unit='ml', cost_per_unit=Decimal('40')
        )
        self.pearl = Ingredient.objects.create(
            tenant=self.tenant, name='Trân châu đen', unit='g', cost_per_unit=Decimal('50')
        )

        other_tenant = Tenant.objects.create(name='Other', public_slug='other-recipe', show_recipe_feature=True)
        self.foreign_ingredient = Ingredient.objects.create(tenant=other_tenant, name='Đường', unit='g')

    def create_order(self, items, *, status=Order.Status.COMPLETED, store=None):
        """items: [(unit, quantity, [toppings])]"""
        order = Order.objects.create(
            tenant=self.tenant,
            store=store or self.store,
            cashier=self.manager,
            payment_method=Order.PaymentMethod.CASH,
            status=status,
            subtotal=Decimal('0'),
            tax_amount=Decimal('0'),
            total_amount=Decimal('0'),
            customer_paid=Decimal('0'),
        )
        for unit, quantity, toppings in items:
            item = OrderItem.objects.create(
                order=order,
                product=unit.product,
                unit=unit,
                snapshot_product_name=unit.product.name,
                snapshot_unit_name=unit.name,
                unit_price=unit.price,
                quantity=quantity,
                line_total=unit.price * quantity,
            )
            for topping in toppings:
                OrderItemTopping.objects.create(
                    order_item=item, topping=topping, snapshot_topping_name=topping.name, snapshot_price=topping.price
                )
        return order


class RecipeFeatureToggleTests(RecipeTestBase):
    def test_empty_post_turns_off_all_features_and_preserves_recipes(self):
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        self.client.force_login(self.manager)
        response = self.client.post(reverse('App_Quanly:feature_settings'), {})
        self.assertRedirects(response, reverse('App_Quanly:feature_settings'))
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.show_recipe_feature)
        self.assertFalse(self.tenant.show_topping_feature)
        self.assertTrue(self.unit_m.recipe_items.exists())

    def test_disallowed_plan_blocks_stale_enabled_flag(self):
        self.tenant.subscription_plan = SubscriptionPlan.objects.get(slug='co-ban')
        self.tenant.save(update_fields=['subscription_plan'])
        self.client.force_login(self.manager)
        for name in ('ingredients', 'recipes', 'ingredient_usage'):
            self.assertEqual(self.client.get(reverse(f'App_Quanly:{name}')).status_code, 403)
        response = self.client.post(
            reverse('App_Quanly:recipe_edit', args=['unit', self.unit_m.pk]),
            {'ingredient_id': [self.coffee.pk], 'quantity': ['18']},
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('App_Quanly:reorder', args=['ingredients']),
            {'ids': [self.coffee.pk]}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RecipeItem.objects.exists())
        self.assertNotContains(
            self.client.get(reverse('App_Quanly:dashboard')),
            f'href="{reverse("App_Quanly:recipes")}"',
        )

    def test_pages_forbidden_when_feature_disabled(self):
        self.tenant.show_recipe_feature = False
        self.tenant.save(update_fields=['show_recipe_feature', 'updated_at'])
        self.client.force_login(self.manager)
        for name in ('ingredients', 'recipes', 'ingredient_usage'):
            self.assertEqual(self.client.get(reverse(f'App_Quanly:{name}')).status_code, 403, name)
        res = self.client.post(
            reverse('App_Quanly:recipe_edit', args=['unit', self.unit_m.id]),
            {'ingredient_id': [self.coffee.id], 'quantity': ['18']},
        )
        self.assertEqual(res.status_code, 403)
        self.assertFalse(RecipeItem.objects.exists())
        html = self.client.get(reverse('App_Quanly:dashboard')).content.decode('utf-8')
        self.assertNotIn(f'href="{reverse("App_Quanly:recipes")}"', html)

    def test_sidebar_and_feature_settings_show_recipe_feature(self):
        self.client.force_login(self.manager)
        html = self.client.get(reverse('App_Quanly:feature_settings')).content.decode('utf-8')
        self.assertIn('name="show_recipe_feature"', html)
        self.assertIn(f'href="{reverse("App_Quanly:recipes")}"', html)

    def test_manager_can_toggle_recipe_feature(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:feature_settings'), {'show_customer_feature': 'on'})
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.show_recipe_feature)
        self.client.post(reverse('App_Quanly:feature_settings'), {'show_recipe_feature': 'on'})
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.show_recipe_feature)

    def test_staff_cannot_access_recipe_pages(self):
        self.client.force_login(self.staff)
        for name in ('ingredients', 'recipes', 'ingredient_usage'):
            self.assertEqual(self.client.get(reverse(f'App_Quanly:{name}')).status_code, 403)
        for name, args, payload in (
            ('ingredients', [], {'name': 'Forbidden', 'unit': 'g'}),
            ('ingredient_edit', [self.coffee.pk], {'name': 'Forbidden', 'unit': 'g'}),
            ('ingredient_delete', [self.coffee.pk], {}),
            ('recipe_edit', ['unit', self.unit_m.pk], {'ingredient_id': [self.coffee.pk], 'quantity': ['1']}),
            ('reorder', ['ingredients'], {}),
        ):
            self.assertEqual(self.client.post(reverse(f'App_Quanly:{name}', args=args), payload).status_code, 403)

    def test_plan_without_recipe_locks_feature(self):
        basic = SubscriptionPlan.objects.get(slug='co-ban')
        pro = SubscriptionPlan.objects.get(slug='chuyen-nghiep')
        self.assertFalse(basic.feature_recipe)
        self.assertTrue(pro.feature_recipe)

        self.tenant.apply_subscription_plan(basic)
        self.tenant.save()
        self.assertFalse(self.tenant.show_recipe_feature)
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:feature_settings'), {'show_recipe_feature': 'on'})
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.show_recipe_feature)

        self.tenant.apply_subscription_plan(pro)
        self.tenant.save()
        self.client.post(reverse('App_Quanly:feature_settings'), {'show_recipe_feature': 'on'})
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.show_recipe_feature)


class IngredientCrudTests(RecipeTestBase):
    def test_empty_create_post_returns_field_errors(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('App_Quanly:ingredients'), {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['form'].errors)
        self.assertIn('unit', response.context['form'].errors)

    def test_changing_unit_in_use_does_not_reinterpret_recipe_quantities(self):
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('App_Quanly:ingredient_edit', args=[self.coffee.pk]),
            {'name': self.coffee.name, 'unit': 'kg', 'cost_per_unit': '350000', 'is_active': 'on'},
            follow=True,
        )
        self.assertContains(response, 'Không thể đổi đơn vị tính')
        self.coffee.refresh_from_db()
        self.assertEqual(self.coffee.unit, 'g')
        self.assertEqual(self.coffee.cost_per_unit, Decimal('350'))

    def test_create_edit_ingredient(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse('App_Quanly:ingredients'),
            {'name': ' Đường cát ', 'unit': 'g', 'cost_per_unit': '25.5', 'is_active': 'on'},
        )
        self.assertRedirects(res, reverse('App_Quanly:ingredients'))
        sugar = Ingredient.objects.get(tenant=self.tenant, name='Đường cát')
        self.assertEqual(sugar.cost_per_unit, Decimal('25.50'))
        self.assertGreater(sugar.display_order, self.pearl.display_order)

        self.client.post(
            reverse('App_Quanly:ingredient_edit', args=[sugar.id]),
            {'name': 'Đường cát', 'unit': 'kg', 'cost_per_unit': '25000'},
        )
        sugar.refresh_from_db()
        self.assertEqual(sugar.unit, 'kg')
        self.assertFalse(sugar.is_active)

    def test_duplicate_name_rejected_case_insensitive(self):
        self.client.force_login(self.manager)
        res = self.client.post(reverse('App_Quanly:ingredients'), {'name': 'cà phê hạt', 'unit': 'g'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Đã có nguyên liệu cùng tên.')
        self.assertEqual(Ingredient.objects.filter(tenant=self.tenant).count(), 3)

    def test_cannot_delete_ingredient_used_in_recipe(self):
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        self.client.force_login(self.manager)
        self.client.post(reverse('App_Quanly:ingredient_delete', args=[self.coffee.id]))
        self.assertTrue(Ingredient.objects.filter(pk=self.coffee.pk).exists())
        self.client.post(reverse('App_Quanly:ingredient_delete', args=[self.milk.id]))
        self.assertFalse(Ingredient.objects.filter(pk=self.milk.pk).exists())

    def test_cannot_edit_other_tenant_ingredient(self):
        self.client.force_login(self.manager)
        self.client.post(
            reverse('App_Quanly:ingredient_edit', args=[self.foreign_ingredient.id]), {'name': 'X', 'unit': 'g'}
        )
        self.foreign_ingredient.refresh_from_db()
        self.assertEqual(self.foreign_ingredient.name, 'Đường')


class RecipeEditTests(RecipeTestBase):
    def test_save_replace_and_clear_unit_recipe(self):
        self.client.force_login(self.manager)
        url = reverse('App_Quanly:recipe_edit', args=['unit', self.unit_m.id])
        self.client.post(url, {'ingredient_id': [self.coffee.id, self.milk.id, ''], 'quantity': ['18', '30,5', '']})
        items = {item.ingredient_id: item.quantity for item in self.unit_m.recipe_items.all()}
        self.assertEqual(items, {self.coffee.id: Decimal('18.000'), self.milk.id: Decimal('30.500')})

        self.client.post(url, {'ingredient_id': [self.coffee.id], 'quantity': ['20']})
        self.assertEqual(list(self.unit_m.recipe_items.values_list('quantity', flat=True)), [Decimal('20.000')])

        self.client.post(url, {'ingredient_id': [''], 'quantity': ['']})
        self.assertFalse(self.unit_m.recipe_items.exists())

    def test_invalid_recipe_keeps_previous_lines(self):
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        self.client.force_login(self.manager)
        url = reverse('App_Quanly:recipe_edit', args=['unit', self.unit_m.id])
        for payload in (
            {'ingredient_id': [self.milk.id], 'quantity': ['0']},
            {'ingredient_id': [self.milk.id], 'quantity': ['abc']},
            {'ingredient_id': [self.milk.id, self.milk.id], 'quantity': ['1', '2']},
            {'ingredient_id': [self.foreign_ingredient.id], 'quantity': ['5']},
            {'ingredient_id': [''], 'quantity': ['5']},
            {'ingredient_id': [self.milk.id], 'quantity': ['0.0001']},
            {'ingredient_id': [self.milk.id], 'quantity': ['1.2345']},
            {'ingredient_id': [self.milk.id], 'quantity': ['NaN']},
            {'ingredient_id': [self.milk.id], 'quantity': ['Infinity']},
            {'ingredient_id': [self.milk.id], 'quantity': ['1000000000']},
            {'ingredient_id': [self.milk.id, self.coffee.id], 'quantity': ['1']},
            {'ingredient_id': [self.milk.id], 'quantity': ['1', '2']},
            {'ingredient_id': [self.milk.id]},
            {'quantity': ['1']},
            {'ingredient_id': ['9' * 100], 'quantity': ['1']},
            {'ingredient_id': ['²'], 'quantity': ['1']},
        ):
            self.client.post(url, payload)
            self.assertEqual(
                list(self.unit_m.recipe_items.values_list('ingredient_id', flat=True)), [self.coffee.id], payload
            )

    def test_service_rejects_foreign_target_even_when_clearing(self):
        foreign_product = Product.objects.create(tenant=self.foreign_ingredient.tenant, name='Foreign')
        foreign_unit = ProductUnit.objects.create(product=foreign_product, name='Ly', price=10000)
        item = RecipeItem.objects.create(product_unit=foreign_unit, ingredient=self.foreign_ingredient, quantity=1)
        with self.assertRaises(ValidationError):
            save_recipe(tenant=self.tenant, product_unit=foreign_unit, rows=[])
        self.assertTrue(RecipeItem.objects.filter(pk=item.pk).exists())

    def test_service_rejects_invalid_quantity_before_replacing(self):
        item = RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=18)
        for quantity in ('0', '-1', '0.0001', 'NaN'):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                save_recipe(tenant=self.tenant, product_unit=self.unit_m, rows=[(self.milk.pk, Decimal(quantity))])
            self.assertTrue(RecipeItem.objects.filter(pk=item.pk).exists())

    def test_model_validation_blocks_invalid_admin_recipes(self):
        for target in ({'product_unit': self.unit_m}, {'topping': self.topping}):
            item = RecipeItem(ingredient=self.foreign_ingredient, quantity=Decimal('1'), **target)
            with self.assertRaises(ValidationError):
                item.full_clean()
        item = RecipeItem(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('0'))
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_missing_filter_excludes_toppings_with_recipe(self):
        RecipeItem.objects.create(topping=self.topping, ingredient=self.pearl, quantity=40)
        missing_topping = Topping.objects.create(tenant=self.tenant, name='Thạch', price=5000)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('App_Quanly:recipes'), {'status': 'missing'})
        self.assertEqual([row['topping'] for row in response.context['topping_rows']], [missing_topping])

    def test_topping_recipe_and_unknown_kind(self):
        self.client.force_login(self.manager)
        self.client.post(
            reverse('App_Quanly:recipe_edit', args=['topping', self.topping.id]),
            {'ingredient_id': [self.pearl.id], 'quantity': ['40']},
        )
        self.assertEqual(self.topping.recipe_items.get().quantity, Decimal('40'))
        self.client.post(
            reverse('App_Quanly:recipe_edit', args=['other', self.topping.id]),
            {'ingredient_id': [self.coffee.id], 'quantity': ['1']},
        )
        self.assertEqual(RecipeItem.objects.count(), 1)

    def test_recipe_page_shows_cost_and_margin(self):
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.milk, quantity=Decimal('30'))
        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:recipes'))
        self.assertEqual(res.status_code, 200)
        # Giá vốn = 18*350 + 30*40 = 7.500; lãi gộp = 25.000 - 7.500 = 17.500 (70%).
        self.assertContains(res, '7.500 đ')
        self.assertContains(res, '17.500 đ')
        self.assertContains(res, '70%')
        self.assertContains(res, 'Chưa có định mức')  # Size L

        missing = self.client.get(reverse('App_Quanly:recipes'), {'status': 'missing'})
        self.assertContains(missing, 'Cà phê sữa')


class IngredientUsageTests(RecipeTestBase):
    def setUp(self):
        super().setUp()
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.coffee, quantity=Decimal('18'))
        RecipeItem.objects.create(product_unit=self.unit_m, ingredient=self.milk, quantity=Decimal('30'))
        RecipeItem.objects.create(product_unit=self.unit_l, ingredient=self.coffee, quantity=Decimal('25'))
        RecipeItem.objects.create(topping=self.topping, ingredient=self.pearl, quantity=Decimal('40'))

    def usage_by_name(self, order_items):
        result = compute_ingredient_usage(order_items)
        return {row['ingredient'].name: row['quantity'] for row in result['rows']}, result

    def test_usage_multiplies_quantity_and_includes_toppings(self):
        self.create_order([(self.unit_m, 2, [self.topping]), (self.unit_l, 1, [])])
        self.create_order([(self.unit_m, 1, [])])
        self.create_order([(self.unit_l, 5, [])], status=Order.Status.CANCELLED)

        items = OrderItem.objects.filter(order__tenant=self.tenant).exclude(order__status=Order.Status.CANCELLED)
        usage, result = self.usage_by_name(items)
        self.assertEqual(usage['Cà phê hạt'], Decimal('79'))  # 3*18 + 1*25
        self.assertEqual(usage['Sữa đặc'], Decimal('90'))  # 3*30
        self.assertEqual(usage['Trân châu đen'], Decimal('80'))  # 2 ly có topping x 40
        self.assertEqual(result['total_cost'], Decimal('79') * 350 + Decimal('90') * 40 + Decimal('80') * 50)
        self.assertEqual(result['missing'], [])

    def test_items_without_recipe_are_reported(self):
        latte = Product.objects.create(tenant=self.tenant, name='Latte')
        latte_unit = ProductUnit.objects.create(product=latte, name='Ly', price=Decimal('40000'))
        self.create_order([(latte_unit, 3, [])])
        _usage, result = self.usage_by_name(OrderItem.objects.filter(order__tenant=self.tenant))
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['missing'], [{'name': 'Latte - Ly', 'sold': 3}])

    def test_usage_page_filters_by_date_and_store(self):
        other_store = Store.objects.create(tenant=self.tenant, name='Store 2')
        self.create_order([(self.unit_m, 1, [])])
        self.create_order([(self.unit_m, 10, [])], store=other_store)
        old = self.create_order([(self.unit_m, 100, [])])
        Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))

        self.client.force_login(self.manager)
        res = self.client.get(reverse('App_Quanly:ingredient_usage'), {'store': self.store.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual([row['quantity'] for row in res.context['usage_rows']], [Decimal('18'), Decimal('30')])

        res = self.client.get(reverse('App_Quanly:ingredient_usage'))
        self.assertContains(res, '198 g')  # 11 ly x 18 g, không tính đơn 30 ngày trước

        res = self.client.get(reverse('App_Quanly:ingredient_usage'), {'date_from': 'bad'})
        self.assertEqual(res.status_code, 200)

    def test_usage_page_paginates_both_tables_independently(self):
        extra = [
            Ingredient.objects.create(tenant=self.tenant, name=f'NL {idx:02d}', unit='g', cost_per_unit=Decimal('1'))
            for idx in range(20)
        ]
        for ingredient in extra:
            RecipeItem.objects.create(product_unit=self.unit_m, ingredient=ingredient, quantity=Decimal('1'))
        missing_units = [
            ProductUnit.objects.create(product=self.product, name=f'Size X{idx:02d}', price=Decimal('1000'))
            for idx in range(21)
        ]
        self.create_order([(self.unit_m, 1, [])] + [(unit, 1, []) for unit in missing_units])

        self.client.force_login(self.manager)
        url = reverse('App_Quanly:ingredient_usage')
        res = self.client.get(url, {'store': self.store.id})
        self.assertEqual(len(res.context['usage_rows']), 20)
        self.assertEqual(res.context['usage_page'].paginator.count, 22)
        self.assertEqual(len(res.context['missing_rows']), 20)
        # Tổng giá vốn luôn tính trên toàn bộ nguyên liệu, không chỉ trang hiện tại.
        self.assertEqual(res.context['total_cost'], Decimal('18') * 350 + Decimal('30') * 40 + 20)
        self.assertContains(res, f'?store={self.store.id}&page=2')
        self.assertContains(res, f'?store={self.store.id}&missing_page=2')

        res = self.client.get(url, {'store': self.store.id, 'page': 2, 'missing_page': 2})
        self.assertEqual(len(res.context['usage_rows']), 2)
        self.assertEqual(len(res.context['missing_rows']), 1)
        # Chuyển trang bảng này giữ nguyên trang của bảng kia.
        self.assertContains(res, f'?store={self.store.id}&amp;missing_page=2&page=1')
        self.assertContains(res, f'?store={self.store.id}&amp;page=2&missing_page=1')

    def test_usage_includes_refunds_and_inactive_ingredients_but_not_cancelled_or_foreign_orders(self):
        self.coffee.is_active = False
        self.coffee.save(update_fields=['is_active'])
        self.create_order([(self.unit_m, 2, [self.topping])], status=Order.Status.REFUNDED)
        self.create_order([(self.unit_m, 100, [])], status=Order.Status.CANCELLED)
        foreign = self.create_order([(self.unit_m, 500, [])])
        Order.objects.filter(pk=foreign.pk).update(tenant=self.foreign_ingredient.tenant)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('App_Quanly:ingredient_usage'))
        quantities = {row['ingredient'].pk: row['quantity'] for row in response.context['usage_rows']}
        self.assertEqual(quantities, {self.coffee.pk: Decimal('36'), self.milk.pk: Decimal('60'), self.pearl.pk: Decimal('80')})

    def test_usage_can_filter_closed_store(self):
        self.store.is_active = False
        self.store.save(update_fields=['is_active'])
        self.create_order([(self.unit_m, 1, [])])
        self.client.force_login(self.manager)
        response = self.client.get(reverse('App_Quanly:ingredient_usage'), {'store': self.store.pk})
        self.assertIn(self.store, response.context['stores'])
        self.assertEqual(response.context['selected_store'], str(self.store.pk))
        self.assertEqual(response.context['total_cost'], Decimal('7500'))

    def test_invalid_filters_reset_visibly(self):
        self.client.force_login(self.manager)
        today = timezone.localdate()
        response = self.client.get(reverse('App_Quanly:ingredient_usage'), {
            'date_from': today.isoformat(), 'date_to': (today - timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.context['date_from'], (today - timedelta(days=6)).isoformat())
        self.assertEqual(response.context['date_to'], today.isoformat())
        self.assertContains(response, 'Ngày lọc không hợp lệ')
        for store_id in ('bad', '9' * 100, str(self.store.pk + 1000)):
            response = self.client.get(reverse('App_Quanly:ingredient_usage'), {'store': store_id})
            self.assertEqual(response.context['selected_store'], '')
            self.assertContains(response, 'Cửa hàng không hợp lệ')

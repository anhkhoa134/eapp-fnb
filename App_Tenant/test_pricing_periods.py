from decimal import Decimal
from django.test import TestCase
from .models import SubscriptionPlan


class PricingPeriodTests(TestCase):
    def test_seeded_monthly_prices_preserve_annual_prices(self):
        for slug, month, year in [('co-ban', 90000, 990000), ('chuyen-nghiep', 199000, 1990000)]:
            with self.subTest(slug=slug):
                plan = SubscriptionPlan.objects.get(slug=slug)
                self.assertEqual(plan.price_monthly, month)
                self.assertEqual(plan.price_yearly, year)
                self.assertEqual(plan.yearly_savings_percent, 17 if slug == 'chuyen-nghiep' else 8)

    def test_savings_follow_configured_prices(self):
        plan = SubscriptionPlan.objects.get(slug='co-ban')
        plan.price_monthly = Decimal('120000')
        plan.save(update_fields=['price_monthly'])
        plan.refresh_from_db()
        self.assertEqual(plan.yearly_savings_percent, 31)
        plan.price_yearly = plan.price_monthly * 12
        self.assertEqual(plan.yearly_savings_percent, 0)
        plan.price_monthly = 0
        self.assertEqual(plan.yearly_savings_percent, 0)

    def test_free_and_contact_plans_have_no_savings(self):
        for slug in ('mien-phi', 'doanh-nghiep'):
            plan = SubscriptionPlan.objects.get(slug=slug)
            self.assertEqual(plan.yearly_savings_percent, 0)

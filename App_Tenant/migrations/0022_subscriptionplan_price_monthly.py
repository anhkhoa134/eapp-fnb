from decimal import Decimal, ROUND_CEILING
from django.core.validators import MinValueValidator
from django.db import migrations, models


def seed_monthly_prices(apps, schema_editor):
    Plan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    for plan in Plan.objects.using(schema_editor.connection.alias).all():
        # Annual billing saves about two months; round monthly prices up to 10,000 VND.
        price = (plan.price_yearly / Decimal('100000')).to_integral_value(rounding=ROUND_CEILING) * 10000
        plan.price_monthly = 0 if plan.is_contact_price else price
        plan.save(using=schema_editor.connection.alias, update_fields=['price_monthly'])


class Migration(migrations.Migration):
    dependencies = [('App_Tenant', '0021_tenant_feature_price_override_enabled_and_more')]
    operations = [
        migrations.AddField(model_name='subscriptionplan', name='price_monthly', field=models.DecimalField('Giá / tháng', max_digits=12, decimal_places=0, default=0, validators=[MinValueValidator(0)])),
        migrations.RunPython(seed_monthly_prices, migrations.RunPython.noop),
    ]

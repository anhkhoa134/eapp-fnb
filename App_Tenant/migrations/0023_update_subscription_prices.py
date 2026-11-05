from django.db import migrations


PRICES = {'co-ban': {'price_monthly': 90000, 'price_yearly': 990000}, 'chuyen-nghiep': {'price_monthly': 199000, 'price_yearly': 1990000}}
PREVIOUS_PRICES = {'co-ban': {'price_monthly': 100000, 'price_yearly': 990000}, 'chuyen-nghiep': {'price_monthly': 200000, 'price_yearly': 1990000}}


def update_prices(apps, schema_editor):
    Plan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    for code, prices in PRICES.items():
        Plan.objects.using(schema_editor.connection.alias).filter(slug=code).update(**prices)


def restore_prices(apps, schema_editor):
    Plan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    for code, prices in PREVIOUS_PRICES.items():
        Plan.objects.using(schema_editor.connection.alias).filter(slug=code).update(**prices)


class Migration(migrations.Migration):
    dependencies = [('App_Tenant', '0022_subscriptionplan_price_monthly')]
    operations = [migrations.RunPython(update_prices, restore_prices)]

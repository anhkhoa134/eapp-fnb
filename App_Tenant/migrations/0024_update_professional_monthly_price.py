from django.db import migrations


def update_monthly_price(apps, schema_editor):
    Plan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    Plan.objects.using(schema_editor.connection.alias).filter(slug='chuyen-nghiep').update(price_monthly=190_000)


def restore_monthly_price(apps, schema_editor):
    Plan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    Plan.objects.using(schema_editor.connection.alias).filter(slug='chuyen-nghiep').update(price_monthly=199_000)


class Migration(migrations.Migration):
    dependencies = [('App_Tenant', '0023_update_subscription_prices')]
    operations = [migrations.RunPython(update_monthly_price, restore_monthly_price)]

from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_TIER_SETTINGS = [
    ('member', Decimal('0'), Decimal('0')),
    ('silver', Decimal('5000000'), Decimal('3')),
    ('gold', Decimal('20000000'), Decimal('5')),
    ('vip', Decimal('50000000'), Decimal('10')),
]


def create_default_tier_settings(apps, schema_editor):
    Tenant = apps.get_model('App_Tenant', 'Tenant')
    CustomerTierSetting = apps.get_model('App_Sales', 'CustomerTierSetting')
    rows = []
    for tenant in Tenant.objects.all():
        existing = set(CustomerTierSetting.objects.filter(tenant=tenant).values_list('tier', flat=True))
        for tier, min_total_spent, discount_percent in DEFAULT_TIER_SETTINGS:
            if tier in existing:
                continue
            rows.append(
                CustomerTierSetting(
                    tenant=tenant,
                    tier=tier,
                    min_total_spent=min_total_spent,
                    discount_percent=discount_percent,
                )
            )
    CustomerTierSetting.objects.bulk_create(rows)


def remove_default_tier_settings(apps, schema_editor):
    CustomerTierSetting = apps.get_model('App_Sales', 'CustomerTierSetting')
    CustomerTierSetting.objects.all().delete()


def backfill_order_discount_source(apps, schema_editor):
    Order = apps.get_model('App_Sales', 'Order')
    Order.objects.filter(discount_amount__gt=0, promotion__isnull=False).update(discount_source='promotion')


class Migration(migrations.Migration):

    dependencies = [
        ('App_Tenant', '0009_store_phone'),
        ('App_Sales', '0008_customer_promotion_order_discount'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerTierSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tier', models.CharField(choices=[('member', 'Member'), ('silver', 'Silver'), ('gold', 'Gold'), ('vip', 'VIP')], max_length=20)),
                ('min_total_spent', models.DecimalField(decimal_places=2, max_digits=14)),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_tier_settings', to='App_Tenant.tenant')),
            ],
            options={
                'verbose_name': 'Cấu hình hạng khách hàng',
                'verbose_name_plural': 'Cấu hình hạng khách hàng',
                'ordering': ['min_total_spent', 'id'],
                'indexes': [
                    models.Index(fields=['tenant', 'tier'], name='App_Sales_c_tenant__8af4bc_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('tenant', 'tier'), name='uq_customer_tier_setting_tenant_tier'),
                ],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='discount_source',
            field=models.CharField(choices=[('none', 'Không giảm'), ('promotion', 'Khuyến mãi'), ('tier', 'Ưu đãi hạng')], default='none', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='tier_discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='order',
            name='tier_discount_percent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='order',
            name='tier_snapshot',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.RunPython(backfill_order_discount_source, migrations.RunPython.noop),
        migrations.RunPython(create_default_tier_settings, remove_default_tier_settings),
    ]

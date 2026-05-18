from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('App_Tenant', '0009_store_phone'),
        ('App_Sales', '0007_order_sale_channel'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('phone', models.CharField(max_length=24)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('note', models.CharField(blank=True, max_length=500)),
                ('is_active', models.BooleanField(default=True, verbose_name='Đang hoạt động')),
                ('points_balance', models.PositiveIntegerField(default=0)),
                ('total_spent', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('tier', models.CharField(choices=[('member', 'Member'), ('silver', 'Silver'), ('gold', 'Gold'), ('vip', 'VIP')], default='member', max_length=20)),
                ('last_order_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customers', to='App_Tenant.tenant')),
            ],
            options={
                'verbose_name': 'Khách hàng',
                'verbose_name_plural': 'Khách hàng',
                'ordering': ['name', 'id'],
                'indexes': [
                    models.Index(fields=['tenant', 'is_active', 'name'], name='App_Sales_c_tenant__f77793_idx'),
                    models.Index(fields=['tenant', 'phone'], name='App_Sales_c_tenant__b981a5_idx'),
                    models.Index(fields=['tenant', 'tier'], name='App_Sales_c_tenant__42ebe9_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('tenant', 'phone'), name='uq_customer_tenant_phone'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('discount_type', models.CharField(choices=[('percent', 'Giảm %'), ('fixed', 'Giảm tiền')], max_length=20)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=14)),
                ('min_order_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('max_discount_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_to', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True, verbose_name='Đang hoạt động')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='App_Tenant.tenant')),
                ('stores', models.ManyToManyField(blank=True, related_name='promotions', to='App_Tenant.store')),
            ],
            options={
                'verbose_name': 'Khuyến mãi',
                'verbose_name_plural': 'Khuyến mãi',
                'ordering': ['-is_active', '-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'is_active'], name='App_Sales_p_tenant__aee46c_idx'),
                    models.Index(fields=['tenant', 'valid_from', 'valid_to'], name='App_Sales_p_tenant__cfc1ff_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='App_Sales.customer'),
        ),
        migrations.AddField(
            model_name='order',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='order',
            name='promotion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='App_Sales.promotion'),
        ),
        migrations.AddField(
            model_name='order',
            name='promotion_snapshot_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='order',
            name='promotion_snapshot_type',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='promotion_snapshot_value',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['tenant', 'customer', 'created_at'], name='App_Sales_o_tenant__b1f442_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['tenant', 'promotion', 'created_at'], name='App_Sales_o_tenant__f4eee8_idx'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App_Tenant', '0010_tenant_feature_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='show_topping_feature',
            field=models.BooleanField(default=True, verbose_name='Hiển thị Topping / tuỳ chọn món'),
        ),
        migrations.AddField(
            model_name='tenant',
            name='show_qr_order_feature',
            field=models.BooleanField(default=True, verbose_name='Hiển thị QR bàn / gọi món QR'),
        ),
    ]

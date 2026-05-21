from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App_Tenant', '0009_store_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='show_customer_feature',
            field=models.BooleanField(default=True, verbose_name='Hiển thị Khách hàng'),
        ),
        migrations.AddField(
            model_name='tenant',
            name='show_promotion_feature',
            field=models.BooleanField(default=True, verbose_name='Hiển thị Khuyến mãi'),
        ),
    ]

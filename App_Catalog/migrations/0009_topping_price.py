from decimal import Decimal

from django.db import migrations, models


def _copy_price_from_product_topping(apps, schema_editor):
    Topping = apps.get_model('App_Catalog', 'Topping')
    ProductTopping = apps.get_model('App_Catalog', 'ProductTopping')

    # Chuyển dữ liệu cũ (giá nằm trên ProductTopping) sang giá chung của Topping.
    # Nếu 1 topping từng có nhiều giá theo sản phẩm, chọn giá lớn nhất để hạn chế "tụt giá" ngoài ý muốn.
    for topping in Topping.objects.all().only('id', 'price'):
        max_price = (
            ProductTopping.objects.filter(topping_id=topping.id).order_by('-price').values_list('price', flat=True).first()
        )
        if max_price is not None:
            # max_price đã là DecimalField trong DB.
            topping.price = max_price
            topping.save(update_fields=['price'])
        else:
            # Không có mapping trước đây → giữ default 0
            if topping.price is None:
                topping.price = Decimal('0')
                topping.save(update_fields=['price'])


class Migration(migrations.Migration):
    dependencies = [
        ('App_Catalog', '0008_is_active_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='topping',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.RunPython(_copy_price_from_product_topping, migrations.RunPython.noop),
    ]


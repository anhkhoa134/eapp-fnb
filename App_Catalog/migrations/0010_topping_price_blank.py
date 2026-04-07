from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('App_Catalog', '0009_topping_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='topping',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=14),
        ),
    ]


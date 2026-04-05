from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App_Sales', '0005_is_active_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='qrorder',
            name='rejection_reason',
            field=models.CharField(blank=True, max_length=500, verbose_name='Lý do từ chối'),
        ),
    ]

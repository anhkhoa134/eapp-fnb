from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App_Sales', '0006_qrorder_rejection_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='sale_channel',
            field=models.CharField(
                blank=True,
                choices=[('dine_in', 'Tại quán'), ('takeaway', 'Mang về')],
                help_text='Thanh toán tại bàn (POS) hay mang về (checkout giỏ). Đơn cũ có thể để trống.',
                max_length=20,
                null=True,
                verbose_name='Kênh bán',
            ),
        ),
    ]

from django.db import migrations


def revoke_admin_staff(apps, schema_editor):
    # Tài khoản của doanh nghiệp không cần vào Django Admin (chỉ superadmin quản trị hệ thống).
    User = apps.get_model('App_Accounts', 'User')
    User.objects.filter(tenant__isnull=False, is_superuser=False, is_staff=True).update(is_staff=False)


class Migration(migrations.Migration):

    dependencies = [
        ('App_Accounts', '0006_rate_limit'),
    ]

    operations = [
        migrations.RunPython(revoke_admin_staff, migrations.RunPython.noop),
    ]

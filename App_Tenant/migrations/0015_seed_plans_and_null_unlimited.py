from django.db import migrations

LIMIT_FIELDS = ('max_stores', 'max_dining_tables', 'max_staff_users')

PLANS = [
    {
        'slug': 'mien-phi',
        'name': 'Miễn phí',
        'price_yearly': 0,
        'is_contact_price': False,
        'tagline': 'Bắt đầu bán hàng ngay, không tốn chi phí.',
        'highlight': '',
        'max_stores': 1,
        'max_staff_users': 0,
        'max_dining_tables': 5,
        'max_products': 20,
        'feature_customer': False,
        'feature_promotion': False,
        'feature_qr_order': False,
        'feature_kitchen': False,
        'is_default': True,
        'sort_order': 1,
    },
    {
        'slug': 'co-ban',
        'name': 'Cơ bản',
        'price_yearly': 990000,
        'is_contact_price': False,
        'tagline': 'Đủ dùng cho một quán hoạt động ổn định.',
        'highlight': '',
        'max_stores': 1,
        'max_staff_users': 5,
        'max_dining_tables': 20,
        'max_products': 100,
        'feature_customer': True,
        'feature_promotion': True,
        'feature_qr_order': True,
        'feature_kitchen': False,
        'is_default': False,
        'sort_order': 2,
    },
    {
        'slug': 'chuyen-nghiep',
        'name': 'Chuyên nghiệp',
        'price_yearly': 1990000,
        'is_contact_price': False,
        'tagline': 'Nhiều chi nhánh, gọi món QR và màn hình bếp đầy đủ.',
        'highlight': 'Phổ biến nhất',
        'max_stores': 3,
        'max_staff_users': 20,
        'max_dining_tables': 60,
        'max_products': 500,
        'feature_customer': True,
        'feature_promotion': True,
        'feature_qr_order': True,
        'feature_kitchen': True,
        'is_default': False,
        'sort_order': 3,
    },
    {
        'slug': 'doanh-nghiep',
        'name': 'Doanh nghiệp',
        'price_yearly': 0,
        'is_contact_price': True,
        'tagline': 'Không giới hạn cửa hàng, hỗ trợ ưu tiên và tuỳ chỉnh riêng.',
        'highlight': '',
        'max_stores': None,
        'max_staff_users': None,
        'max_dining_tables': None,
        'max_products': None,
        'feature_customer': True,
        'feature_promotion': True,
        'feature_qr_order': True,
        'feature_kitchen': True,
        'is_default': False,
        'sort_order': 4,
    },
]


def zero_to_null(apps, schema_editor):
    # Trước đây 0 = không giới hạn; nay để trống = không giới hạn, 0 = không có.
    Tenant = apps.get_model('App_Tenant', 'Tenant')
    for field in LIMIT_FIELDS:
        Tenant.objects.filter(**{field: 0}).update(**{field: None})


def null_to_zero(apps, schema_editor):
    Tenant = apps.get_model('App_Tenant', 'Tenant')
    for field in LIMIT_FIELDS:
        Tenant.objects.filter(**{f'{field}__isnull': True}).update(**{field: 0})


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    for plan in PLANS:
        data = dict(plan)
        SubscriptionPlan.objects.update_or_create(slug=data.pop('slug'), defaults=data)


def unseed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('App_Tenant', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(slug__in=[plan['slug'] for plan in PLANS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('App_Tenant', '0014_subscription_plans'),
    ]

    operations = [
        migrations.RunPython(zero_to_null, null_to_zero),
        migrations.RunPython(seed_plans, unseed_plans),
    ]

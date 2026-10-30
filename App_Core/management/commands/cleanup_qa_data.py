# python manage.py cleanup_qa_data --tenant demo            (xem trước, không ghi gì)
# python manage.py cleanup_qa_data --tenant demo --apply    (tắt dữ liệu test thật sự)
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from App_Catalog.models import Category, Ingredient, Product, ProductUnit, Topping
from App_Sales.models import Customer, DiningTable, Promotion, generate_qr_token
from App_Tenant.models import Tenant


class Command(BaseCommand):
    help = (
        'Tắt (không xoá) dữ liệu do người kiểm thử tạo, nhận diện bằng tiền tố tên (mặc định "QA-TEST"): '
        'khuyến mãi, bàn QR (đổi luôn token), món, đơn vị bán, topping, danh mục, nguyên liệu, khách hàng. '
        'Đơn hàng và nhật ký giữ nguyên để không lệch số liệu.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='public_slug của doanh nghiệp, VD: demo')
        parser.add_argument('--prefix', default='QA-TEST', help='Tiền tố tên dữ liệu test (mặc định QA-TEST)')
        parser.add_argument('--apply', action='store_true', help='Ghi thay đổi. Không có cờ này thì chỉ liệt kê.')

    def handle(self, *args, tenant, prefix, apply, **options):
        prefix = prefix.strip()
        if len(prefix) < 3:
            raise CommandError('Tiền tố quá ngắn, dễ tắt nhầm dữ liệu thật.')
        tenant_obj = Tenant.objects.filter(public_slug=tenant).first()
        if tenant_obj is None:
            raise CommandError(f'Không có doanh nghiệp "{tenant}".')

        groups = [
            ('Khuyến mãi', Promotion.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
            ('Món', Product.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
            (
                'Đơn vị bán',
                ProductUnit.objects.filter(product__tenant=tenant_obj, name__startswith=prefix, is_active=True),
            ),
            ('Topping', Topping.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
            ('Danh mục', Category.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
            ('Nguyên liệu', Ingredient.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
            ('Khách hàng', Customer.objects.filter(tenant=tenant_obj, name__startswith=prefix, is_active=True)),
        ]
        tables = DiningTable.objects.filter(tenant=tenant_obj, name__startswith=prefix) | DiningTable.objects.filter(
            tenant=tenant_obj, code__startswith=prefix.upper()
        )

        total = 0
        for label, queryset in groups:
            rows = list(queryset)
            total += len(rows)
            for row in rows:
                self.stdout.write(f'  {label}: {row}')
        table_rows = list(tables.distinct())
        total += len(table_rows)
        for table in table_rows:
            self.stdout.write(f'  Bàn QR: {table.code} – {table.name} (tắt + đổi token)')

        if not total:
            self.stdout.write(self.style.SUCCESS(f'Không có dữ liệu "{prefix}" nào đang bật ở {tenant_obj.name}.'))
            return
        if not apply:
            self.stdout.write(self.style.WARNING(f'Xem trước {total} mục. Chạy lại với --apply để tắt.'))
            return

        with transaction.atomic():
            for _label, queryset in groups:
                # save() từng dòng để chạy validation của model như khi tắt trên giao diện.
                for row in queryset:
                    row.is_active = False
                    row.save()
            for table in table_rows:
                table.is_active = False
                table.qr_token = generate_qr_token()
                table.save()
        self.stdout.write(self.style.SUCCESS(f'Đã tắt {total} mục dữ liệu "{prefix}" ở {tenant_obj.name}.'))

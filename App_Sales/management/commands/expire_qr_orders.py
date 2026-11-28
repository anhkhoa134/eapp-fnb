from django.core.management.base import BaseCommand

from App_Sales.qr_expiry import QR_ORDER_PENDING_MINUTES, expire_stale_qr_orders


class Command(BaseCommand):
    help = f'Huỷ đơn QR chờ duyệt quá {QR_ORDER_PENDING_MINUTES} phút (FNB-11). Có thể chạy theo cron mỗi 5 phút.'

    def handle(self, *args, **options):
        count = expire_stale_qr_orders()
        self.stdout.write(self.style.SUCCESS(f'Đã huỷ {count} đơn QR quá hạn.'))

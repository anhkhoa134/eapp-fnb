# python manage.py reset_demo_data  (chạy định kỳ bằng systemd timer, xem docs/setup/6_production_env.md)
from django.core.management.base import BaseCommand

from App_Core.seed_initial_data_runner import reset_demo_tenant


class Command(BaseCommand):
    help = 'Xoá sạch doanh nghiệp demo (tài khoản hiện ở trang đăng nhập) và seed lại từ đầu.'

    def handle(self, *args, **options):
        reset_demo_tenant(stdout=self.stdout, style=self.style)

# python manage.py reset_demo_data [--older-than-days 2.5]
# Chạy định kỳ bằng Coolify Scheduled Task (mỗi ngày, --older-than-days 2.5 → thực tế khoảng 3 ngày một lần).
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from App_Core.demo import DemoOnlyCommandMixin
from App_Core.seed_initial_data_runner import reset_demo_tenant
from App_Tenant.models import Tenant


class Command(DemoOnlyCommandMixin, BaseCommand):
    help = 'Xoá sạch doanh nghiệp demo (tài khoản hiện ở trang đăng nhập) và seed lại từ đầu.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-days',
            type=float,
            default=0,
            help='Chỉ reset khi lần reset trước (Tenant.created_at) đã quá N ngày. 0 = luôn reset.',
        )

    def handle(self, *args, **options):
        days = options['older_than_days']
        tenant = Tenant.objects.filter(public_slug=settings.DEMO_TENANT_SLUG).first()
        if tenant is not None and days > 0:
            age = timezone.now() - tenant.created_at
            if age < timedelta(days=days):
                self.stdout.write(f'Bỏ qua: tenant demo mới reset {age.days} ngày trước (< {days:g} ngày).')
                return
        reset_demo_tenant(stdout=self.stdout, style=self.style)

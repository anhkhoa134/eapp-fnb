# python manage.py cleanup_auth_throttle  (chạy định kỳ bằng systemd timer, xem docs/setup/6_production_env.md)
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from App_Accounts.models import LoginAttempt, RateLimit


class Command(BaseCommand):
    help = 'Xoá bộ đếm đăng nhập sai / giới hạn tần suất đã hết hạn để bảng không phình to.'

    def handle(self, *args, **options):
        now = timezone.now()
        lockout_window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        attempts, _ = (
            LoginAttempt.objects.filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
            .filter(Q(last_failure_at__isnull=True) | Q(last_failure_at__lt=now - lockout_window))
            .delete()
        )
        # Cửa sổ dài nhất đang dùng là SIGNUP_WINDOW_HOURS.
        longest_window = max(lockout_window, timedelta(hours=settings.SIGNUP_WINDOW_HOURS), timedelta(hours=1))
        buckets, _ = RateLimit.objects.filter(window_started_at__lt=now - longest_window).delete()
        self.stdout.write(self.style.SUCCESS(f'Đã xoá {attempts} bản ghi đăng nhập sai, {buckets} bộ đếm tần suất.'))

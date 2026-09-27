"""Giới hạn tần suất theo IP (cửa sổ cố định, lưu DB để dùng chung giữa các worker)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from App_Accounts.models import RateLimit

SCOPE_LOGIN_IP = 'login_ip'
SCOPE_SIGNUP_IP = 'signup_ip'
SCOPE_PASSWORD_RESET_IP = 'password_reset_ip'
SCOPE_TAKEAWAY_ORDER_IP = 'takeaway_order_ip'


def limited_until(scope, key, *, limit, window: timedelta):
    """Thời điểm được thử lại nếu đã chạm giới hạn trong cửa sổ hiện tại, ngược lại None."""
    bucket = RateLimit.objects.filter(scope=scope, key=key).first()
    if bucket is None or bucket.count < limit:
        return None
    until = bucket.window_started_at + window
    return until if until > timezone.now() else None


def hit(scope, key, *, window: timedelta):
    """Tăng bộ đếm; cửa sổ đã hết hạn thì đếm lại từ đầu."""
    now = timezone.now()
    with transaction.atomic():
        bucket, _ = RateLimit.objects.select_for_update().get_or_create(
            scope=scope,
            key=key,
            defaults={'window_started_at': now},
        )
        if now - bucket.window_started_at > window:
            bucket.count = 0
            bucket.window_started_at = now
        bucket.count += 1
        bucket.save(update_fields=['count', 'window_started_at'])


def minutes_until(until) -> int:
    return max(1, -(-int((until - timezone.now()).total_seconds()) // 60))

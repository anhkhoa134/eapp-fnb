"""Khoá tạm đăng nhập theo username + IP sau nhiều lần sai (BL-002)."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from App_Accounts.models import LoginAttempt


def _failure_limit() -> int:
    return settings.LOGIN_FAILURE_LIMIT


def _lockout_window() -> timedelta:
    return timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def normalize_username(username) -> str:
    return (username or '').strip().lower()[:150]


def get_client_ip(request) -> str:
    if request is None:
        return ''
    if settings.LOGIN_TRUST_X_REAL_IP:
        real_ip = (request.META.get('HTTP_X_REAL_IP') or '').strip()
        if real_ip:
            return real_ip[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def locked_until(username, ip_address):
    """Thời điểm hết khoá nếu đang bị khoá, ngược lại None."""
    attempt = LoginAttempt.objects.filter(
        username=normalize_username(username),
        ip_address=ip_address,
        locked_until__gt=timezone.now(),
    ).first()
    return attempt.locked_until if attempt else None


def record_failure(username, ip_address):
    """Ghi nhận 1 lần sai. Trả về thời điểm hết khoá nếu lần này làm tài khoản bị khoá."""
    now = timezone.now()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
            username=normalize_username(username),
            ip_address=ip_address,
        )
        # Lần sai cũ đã quá cửa sổ thời gian thì đếm lại từ đầu.
        if attempt.last_failure_at is None or now - attempt.last_failure_at > _lockout_window():
            attempt.failure_count = 0
        attempt.failure_count += 1
        attempt.last_failure_at = now
        if attempt.failure_count >= _failure_limit():
            attempt.locked_until = now + _lockout_window()
            attempt.failure_count = 0
        attempt.save()
    if attempt.locked_until and attempt.locked_until > now:
        return attempt.locked_until
    return None


def reset(username, ip_address):
    LoginAttempt.objects.filter(username=normalize_username(username), ip_address=ip_address).delete()

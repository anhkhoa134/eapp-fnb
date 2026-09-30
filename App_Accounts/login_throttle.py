"""Khoá tạm đăng nhập theo username + IP sau nhiều lần sai (BL-002)."""

from datetime import timedelta
from ipaddress import ip_address

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


def _normalize_ip(raw) -> str:
    raw = (raw or '').strip()
    # Scoped IPv6 addresses are not suitable for the database's inet column.
    if '%' in raw:
        return ''
    try:
        return str(ip_address(raw))
    except ValueError:
        return ''


def get_client_ip(request) -> str:
    """Return one valid IP, or empty when the request has no usable address."""
    if request is None:
        return ''
    if settings.LOGIN_TRUST_X_REAL_IP:
        # Proxies can emit the same X-Real-IP header more than once; the server
        # combines them with commas. Accept identical IPs, but don't guess when
        # the header contains conflicting addresses or malformed values.
        real_ips = {
            _normalize_ip(value)
            for value in (request.META.get('HTTP_X_REAL_IP') or '').split(',')
        }
        if len(real_ips) == 1 and '' not in real_ips:
            return real_ips.pop()
    return _normalize_ip(request.META.get('REMOTE_ADDR'))


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

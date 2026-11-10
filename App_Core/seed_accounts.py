"""Cờ tạo tài khoản cho lệnh seed: phân biệt tài khoản demo công khai và superadmin riêng.

- --demo: tài khoản demo dùng chung (mật khẩu in ở trang đăng nhập) — KHÔNG bao giờ là staff/superuser.
- --superadmin: Django superuser riêng của chủ site (vào trang quản trị). Mật khẩu lấy từ --superadmin-password hoặc
  biến SUPERADMIN_PASSWORD; máy dev mặc định "123", production bắt buộc mật khẩu mạnh, khác mật khẩu demo.
Không truyền cờ nào = --demo (giữ hành vi cũ). Chỉ --superadmin thì không cần ALLOW_DEMO_SEED ở production.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

DEV_SUPERADMIN_PASSWORD = '123'
EXTRA_FLAGS = ()  # demoweb thêm 'quanly'


def is_dev():
    return str(getattr(settings, 'ENVIRONMENT', '')).lower() in {'dev', 'development'}


def add_account_flags(parser, *, extra_flags=EXTRA_FLAGS):
    group = parser.add_argument_group('Tài khoản')
    group.add_argument('--demo', action='store_true', help='Tạo/cập nhật tài khoản demo công khai (không staff/superuser).')
    for flag in extra_flags:
        group.add_argument(f'--{flag}', action='store_true', help=f'Tạo/cập nhật tài khoản {flag}.')
    group.add_argument('--superadmin', action='store_true', help='Tạo/cập nhật Django superuser riêng (không phải demo).')
    group.add_argument('--superadmin-username', default='superadmin')
    group.add_argument(
        '--superadmin-password', default=None,
        help='Mật khẩu superadmin (hoặc env SUPERADMIN_PASSWORD). Dev mặc định "123"; production bắt buộc, phải mạnh.',
    )


def wants(options, flag, *, extra_flags=EXTRA_FLAGS):
    """Không cờ tài khoản nào → mặc định --demo."""
    flags = ('demo', 'superadmin', *extra_flags)
    if not any(options.get(name) for name in flags):
        return flag == 'demo'
    return bool(options.get(flag))


def ensure_superadmin(options, *, demo_usernames=(), demo_password='123456', stdout=None):
    username = (options.get('superadmin_username') or 'superadmin').strip()
    if username in set(demo_usernames):
        raise CommandError(f'"{username}" là tài khoản demo dùng chung, không dùng làm superadmin.')
    password = options.get('superadmin_password') or os.environ.get('SUPERADMIN_PASSWORD') or ''
    if not password:
        if not is_dev():
            raise CommandError('Production cần --superadmin-password hoặc biến SUPERADMIN_PASSWORD (mật khẩu mạnh).')
        password = DEV_SUPERADMIN_PASSWORD
    elif not is_dev():
        if password == demo_password:
            raise CommandError('Mật khẩu superadmin không được trùng mật khẩu demo công khai.')
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('Mật khẩu superadmin chưa đủ mạnh: ' + ' '.join(error.messages))

    User = get_user_model()
    user = User.objects.filter(**{User.USERNAME_FIELD: username}).first()
    created = user is None
    if created:
        user = User(**{User.USERNAME_FIELD: username})
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()
    if stdout is not None:
        shown = password if is_dev() else '(mật khẩu đã nhập)'
        stdout.write(f"{'Đã tạo' if created else 'Đã cập nhật'} superadmin: {username} / {shown}")
    return user


def demo_guard_needed(options, *, extra_flags=EXTRA_FLAGS):
    """Lệnh chỉ tạo superadmin thì không phải dữ liệu demo: bỏ qua ALLOW_DEMO_SEED."""
    return any(wants(options, flag, extra_flags=extra_flags) for flag in ('demo', *extra_flags))

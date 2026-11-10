"""Tài khoản demo dùng chung trên site công khai (DEMO_MODE=1).

Mật khẩu demo in sẵn ở trang đăng nhập nên ai cũng đăng nhập được. Khách dùng thử vẫn tạo/sửa dữ liệu demo tùy ý
(`manage.py reset_demo_data` dọn định kỳ), nhưng không được đổi mật khẩu, email, vai trò, trạng thái hay xoá chính
các tài khoản dùng chung — nếu không người dùng thử sau sẽ bị khoá ngoài tới lần reset kế tiếp.
"""
import os

from django.conf import settings
from django.core.management.base import CommandError

SHARED_DEMO_ACCOUNT_MESSAGE = (
    'Đây là tài khoản demo dùng chung nên không đổi được mật khẩu, email, vai trò hay trạng thái. '
    'Hãy đăng ký cửa hàng riêng để dùng đầy đủ.'
)
# Tài khoản do seed_initial_data tạo cho tenant demo: <slug>_quanly, <slug>_nhanvien_1..4.
DEMO_ACCOUNT_SUFFIXES = ('quanly', 'nhanvien_1', 'nhanvien_2', 'nhanvien_3', 'nhanvien_4')


def shared_demo_usernames():
    return frozenset(f'{settings.DEMO_TENANT_SLUG}_{suffix}' for suffix in DEMO_ACCOUNT_SUFFIXES)


def is_shared_demo_account(user):
    return bool(settings.DEMO_MODE and user is not None and getattr(user, 'username', None) in shared_demo_usernames())


class DemoOnlyCommandMixin:
    """Chặn lệnh xoá/seed lại dữ liệu demo khi ENVIRONMENT=prod, trừ site đặt ALLOW_DEMO_SEED=1.

    Kiểm trong execute() để guard chạy trước khi chạm DB.
    """

    def execute(self, *args, **options):
        if settings.ENVIRONMENT == 'prod' and os.environ.get('ALLOW_DEMO_SEED') != '1':
            raise CommandError(
                'Không chạy lệnh dữ liệu demo khi ENVIRONMENT=prod. Đặt ALLOW_DEMO_SEED=1 nếu đây là site có tenant demo.'
            )
        return super().execute(*args, **options)

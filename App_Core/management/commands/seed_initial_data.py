# python manage.py seed_initial_data [--demo] [--superadmin [--superadmin-password ...]]
#   --demo (mặc định khi không truyền cờ nào): tenant demo + tài khoản demo_quanly, demo_nhanvien_1..4 (không staff).
#   --superadmin: Django superuser riêng của chủ site (production bắt buộc mật khẩu mạnh, không cần ALLOW_DEMO_SEED).
# Ví dụ dev: python manage.py seed_initial_data --demo --superadmin --reset-passwords
from django.core.management.base import BaseCommand

from App_Core.demo import DemoOnlyCommandMixin, shared_demo_usernames
from App_Core.seed_accounts import add_account_flags, demo_guard_needed, ensure_superadmin, wants
from App_Core.seed_initial_data_runner import add_seed_initial_data_arguments, run_seed_initial_data


class Command(DemoOnlyCommandMixin, BaseCommand):
    help = 'Seed dữ liệu demo (doanh nghiệp/cửa hàng/user/catalog/bàn/đơn QR mẫu) và/hoặc superadmin.'

    def add_arguments(self, parser):
        add_seed_initial_data_arguments(parser)
        add_account_flags(parser)

    def execute(self, *args, **options):
        if not demo_guard_needed(options):
            return BaseCommand.execute(self, *args, **options)
        return super().execute(*args, **options)

    def handle(self, *args, **options):
        if wants(options, 'demo'):
            run_seed_initial_data(
                stdout=self.stdout,
                style=self.style,
                tenant_slug=options['tenant_slug'],
                tenant_name=options['tenant_name'],
                default_password=options['default_password'],
                reset_passwords=options['reset_passwords'],
                seed_qr_pending=options['seed_qr_pending'],
                skip_qr_pending=options['skip_qr_pending'],
            )
        if wants(options, 'superadmin'):
            ensure_superadmin(
                options,
                demo_usernames=shared_demo_usernames(),
                demo_password=options['default_password'],
                stdout=self.stdout,
            )

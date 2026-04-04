# python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
from django.core.management.base import BaseCommand

from App_Core.seed_initial_data_runner import add_seed_initial_data_arguments, run_seed_initial_data


class Command(BaseCommand):
    help = 'Seed dữ liệu tenant/store/user/catalog/table/qr mẫu (idempotent, compact-plus).'

    def add_arguments(self, parser):
        add_seed_initial_data_arguments(parser)

    def handle(self, *args, **options):
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

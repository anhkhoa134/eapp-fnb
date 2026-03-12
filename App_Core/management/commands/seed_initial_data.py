from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Tenant.models import Store, Tenant, UserStoreAccess


class Command(BaseCommand):
    help = 'Seed dữ liệu tenant/store/user/catalog mẫu (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-slug', default='demo')
        parser.add_argument('--tenant-name', default='Demo FNB')
        parser.add_argument('--default-password', default='123456')
        parser.add_argument('--reset-passwords', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        tenant_name = options['tenant_name']
        default_password = options['default_password']
        reset_passwords = options['reset_passwords']

        User = get_user_model()

        tenant, _ = Tenant.objects.update_or_create(
            public_slug=tenant_slug,
            defaults={'name': tenant_name, 'is_active': True},
        )

        stores_seed = [
            {'name': 'CN Trung Tâm', 'address': '01 Nguyễn Huệ, Q1, TP.HCM', 'is_default': True},
            {'name': 'CN Thủ Đức', 'address': '45 Võ Văn Ngân, TP. Thủ Đức, TP.HCM', 'is_default': False},
            {'name': 'CN Gò Vấp', 'address': '120 Quang Trung, Q. Gò Vấp, TP.HCM', 'is_default': False},
        ]
        store_map = {}
        for row in stores_seed:
            store, _ = Store.objects.get_or_create(
                tenant=tenant,
                name=row['name'],
                defaults={'address': row['address'], 'is_active': True, 'is_default': False},
            )
            store.address = row['address']
            store.is_active = True
            store.is_default = False
            store.save(update_fields=['address', 'is_active', 'is_default', 'updated_at'])
            store_map[row['name']] = store

        Store.objects.filter(tenant=tenant).update(is_default=False)
        default_store = store_map['CN Trung Tâm']
        default_store.is_default = True
        default_store.save(update_fields=['is_default', 'updated_at'])

        manager, manager_created = User.objects.get_or_create(
            username=f'{tenant_slug}_quanly',
            defaults={'tenant': tenant, 'role': User.Role.MANAGER, 'is_staff': True, 'is_active': True},
        )
        manager.tenant = tenant
        manager.role = User.Role.MANAGER
        manager.is_staff = True
        manager.is_active = True
        manager.save(update_fields=['tenant', 'role', 'is_staff', 'is_active'])
        if manager_created or reset_passwords:
            manager.set_password(default_password)
            manager.save(update_fields=['password'])

        staff_rows = [
            (f'{tenant_slug}_nhanvien_1', ['CN Trung Tâm', 'CN Thủ Đức'], 'CN Trung Tâm'),
            (f'{tenant_slug}_nhanvien_2', ['CN Thủ Đức', 'CN Gò Vấp'], 'CN Thủ Đức'),
        ]
        staff_users = []
        for username, _, _ in staff_rows:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'tenant': tenant, 'role': User.Role.STAFF, 'is_staff': False, 'is_active': True},
            )
            user.tenant = tenant
            user.role = User.Role.STAFF
            user.is_staff = False
            user.is_active = True
            user.save(update_fields=['tenant', 'role', 'is_staff', 'is_active'])
            if created or reset_passwords:
                user.set_password(default_password)
                user.save(update_fields=['password'])
            staff_users.append(user)

        self._sync_access(manager, [r['name'] for r in stores_seed], 'CN Trung Tâm', store_map)
        for idx, staff in enumerate(staff_users):
            self._sync_access(staff, staff_rows[idx][1], staff_rows[idx][2], store_map)

        categories_seed = ['Đồ ăn', 'Nước uống', 'Combo']
        category_map = {}
        for cat_name in categories_seed:
            category, _ = Category.objects.get_or_create(tenant=tenant, name=cat_name, defaults={'is_active': True})
            category.description = f'Danh mục {cat_name}'
            category.is_active = True
            category.save(update_fields=['description', 'is_active', 'updated_at'])
            category_map[cat_name] = category
            for store in store_map.values():
                StoreCategory.objects.update_or_create(
                    store=store,
                    category=category,
                    defaults={'is_visible': True},
                )

        products_seed = [
            {
                'name': 'Cà phê sữa đá',
                'category': 'Nước uống',
                'image_url': 'https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=600&q=80',
                'stores': ['CN Trung Tâm', 'CN Thủ Đức', 'CN Gò Vấp'],
                'units': [('M', Decimal('29000')), ('L', Decimal('35000'))],
            },
            {
                'name': 'Trà đào cam sả',
                'category': 'Nước uống',
                'image_url': 'https://images.unsplash.com/photo-1499638673689-79a0b5115d87?auto=format&fit=crop&w=600&q=80',
                'stores': ['CN Trung Tâm', 'CN Thủ Đức'],
                'units': [('M', Decimal('45000')), ('L', Decimal('55000'))],
            },
            {
                'name': 'Bánh mì thịt nướng',
                'category': 'Đồ ăn',
                'image_url': 'https://images.unsplash.com/photo-1509722747041-616f39b57569?auto=format&fit=crop&w=600&q=80',
                'stores': ['CN Trung Tâm', 'CN Gò Vấp'],
                'units': [('Phần', Decimal('25000'))],
            },
            {
                'name': 'Combo sáng',
                'category': 'Combo',
                'image_url': 'https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?auto=format&fit=crop&w=600&q=80',
                'stores': ['CN Trung Tâm', 'CN Thủ Đức', 'CN Gò Vấp'],
                'units': [('Combo', Decimal('65000'))],
            },
        ]

        for row in products_seed:
            product, _ = Product.objects.get_or_create(
                tenant=tenant,
                name=row['name'],
                defaults={
                    'category': category_map[row['category']],
                    'short_description': row['name'],
                    'description': f'Sản phẩm {row["name"]}',
                    'image_url': row['image_url'],
                    'is_active': True,
                },
            )
            product.category = category_map[row['category']]
            product.short_description = row['name']
            product.description = f'Sản phẩm {row["name"]}'
            product.image_url = row['image_url']
            product.is_active = True
            product.save()

            for idx, (unit_name, unit_price) in enumerate(row['units'], start=1):
                ProductUnit.objects.update_or_create(
                    product=product,
                    name=unit_name,
                    defaults={
                        'price': unit_price,
                        'display_order': idx,
                        'is_active': True,
                    },
                )

            for store in store_map.values():
                StoreProduct.objects.update_or_create(
                    store=store,
                    product=product,
                    defaults={'is_available': store.name in row['stores']},
                )

        self.stdout.write(self.style.SUCCESS('Seed dữ liệu thành công.'))
        self.stdout.write(f'Tenant: {tenant.public_slug} ({tenant.name})')
        self.stdout.write(f'Manager: {manager.username}')
        self.stdout.write(f'Staff: {", ".join(u.username for u in staff_users)}')

    def _sync_access(self, user, store_names, default_store_name, store_map):
        allowed_ids = [store_map[name].id for name in store_names]
        UserStoreAccess.objects.filter(user=user).exclude(store_id__in=allowed_ids).delete()

        for store_name in store_names:
            UserStoreAccess.objects.update_or_create(
                user=user,
                store=store_map[store_name],
                defaults={'is_default': store_name == default_store_name},
            )

        UserStoreAccess.objects.filter(user=user).exclude(store=store_map[default_store_name]).update(is_default=False)

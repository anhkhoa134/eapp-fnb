from argparse import BooleanOptionalAction
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable, QROrder, QROrderItem
from App_Sales.services import get_effective_unit_price
from App_Tenant.models import Store, Tenant, UserStoreAccess


class Command(BaseCommand):
    help = 'Seed dữ liệu tenant/store/user/catalog/table/qr mẫu (idempotent, compact-plus).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-slug', default='demo')
        parser.add_argument('--tenant-name', default='Demo FNB')
        parser.add_argument('--default-password', default='123456')
        parser.add_argument('--reset-passwords', action='store_true')
        parser.add_argument(
            '--seed-qr-pending',
            action=BooleanOptionalAction,
            default=True,
            help='Seed thêm đơn QR pending để demo tab online (mặc định bật).',
        )
        parser.add_argument(
            '--skip-qr-pending',
            action='store_true',
            help='Alias cũ: tắt seed QR pending (tương đương --no-seed-qr-pending).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        tenant_name = options['tenant_name']
        default_password = options['default_password']
        reset_passwords = options['reset_passwords']
        seed_qr_pending = options['seed_qr_pending'] and not options['skip_qr_pending']

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
            (f'{tenant_slug}_nhanvien_3', ['CN Trung Tâm', 'CN Gò Vấp'], 'CN Gò Vấp'),
            (f'{tenant_slug}_nhanvien_4', ['CN Trung Tâm'], 'CN Trung Tâm'),
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

        self._sync_access(manager, [row['name'] for row in stores_seed], 'CN Trung Tâm', store_map)
        for idx, staff in enumerate(staff_users):
            self._sync_access(staff, staff_rows[idx][1], staff_rows[idx][2], store_map)

        categories_seed = [
            'Đồ ăn',
            'Nước uống',
            'Combo',
            'Trà sữa',
            'Cà phê',
            'Tráng miệng',
            'Đồ chay',
            'Ăn vặt',
        ]
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

        product_templates = {
            'Đồ ăn': ['Cơm gà', 'Bún bò', 'Mì xào', 'Phở bò', 'Gà rán', 'Bánh mì', 'Cơm tấm', 'Xôi mặn'],
            'Nước uống': ['Nước cam', 'Nước chanh', 'Soda', 'Trà đào', 'Sinh tố dâu', 'Nước ép thơm', 'Bạc hà đá', 'Nước dừa'],
            'Combo': ['Combo sáng', 'Combo trưa', 'Combo tối', 'Combo gia đình', 'Combo văn phòng', 'Combo tiết kiệm', 'Combo đôi', 'Combo party'],
            'Trà sữa': ['Trà sữa truyền thống', 'Trà sữa trân châu', 'Trà sữa khoai môn', 'Trà sữa matcha', 'Trà sữa socola', 'Trà sữa dâu', 'Trà sữa ô long', 'Trà sữa kem cheese'],
            'Cà phê': ['Espresso', 'Americano', 'Latte', 'Cappuccino', 'Cà phê đen', 'Cà phê sữa', 'Cold brew', 'Mocha'],
            'Tráng miệng': ['Bánh flan', 'Tiramisu', 'Panna cotta', 'Bánh mousse', 'Rau câu', 'Bánh su kem', 'Sữa chua', 'Kem ly'],
            'Đồ chay': ['Cơm chay', 'Bún chay', 'Mì chay', 'Gỏi cuốn chay', 'Lẩu chay', 'Đậu hũ sốt', 'Nấm kho', 'Cà ri chay'],
            'Ăn vặt': ['Khoai tây chiên', 'Cá viên chiên', 'Bắp xào', 'Phô mai que', 'Há cảo', 'Nem chua rán', 'Bánh tráng trộn', 'Xúc xích'],
        }

        product_counter = 0
        product_ids = []
        for category_name, names in product_templates.items():
            category = category_map[category_name]
            for idx, base_name in enumerate(names, start=1):
                product_counter += 1
                product_name = f'{base_name} {idx:02d}'
                product, _ = Product.objects.get_or_create(
                    tenant=tenant,
                    name=product_name,
                    defaults={
                        'category': category,
                        'short_description': f'{base_name} chuẩn vị',
                        'description': f'Sản phẩm {product_name}',
                        'image_url': f'https://placehold.co/600x600/png?text={product_name.replace(" ", "+")}',
                        'is_active': True,
                    },
                )
                product.category = category
                product.short_description = f'{base_name} chuẩn vị'
                product.description = f'Sản phẩm {product_name}'
                product.image_url = f'https://placehold.co/600x600/png?text={product_name.replace(" ", "+")}'
                product.is_active = True
                product.save()
                product_ids.append(product.id)

                units_seed = [
                    ('M', Decimal(str(25000 + (product_counter % 7) * 4000))),
                    ('L', Decimal(str(32000 + (product_counter % 7) * 4000))),
                ]
                if category_name in {'Đồ ăn', 'Combo', 'Đồ chay', 'Ăn vặt'}:
                    units_seed = [
                        ('Phần', Decimal(str(35000 + (product_counter % 8) * 5000))),
                    ]

                for unit_order, (unit_name, unit_price) in enumerate(units_seed, start=1):
                    ProductUnit.objects.update_or_create(
                        product=product,
                        name=unit_name,
                        defaults={
                            'price': unit_price,
                            'display_order': unit_order,
                            'is_active': True,
                        },
                    )

                store_names = list(store_map.keys())
                active_store_count = 1 + (product_counter % 3)
                assigned_stores = set(store_names[:active_store_count])
                if product_counter % 2 == 0:
                    assigned_stores.add('CN Gò Vấp')

                for store in store_map.values():
                    StoreProduct.objects.update_or_create(
                        store=store,
                        product=product,
                        defaults={'is_available': store.name in assigned_stores},
                    )

        for store in store_map.values():
            for idx in range(1, 13):
                code = f'{store.slug[:3].upper()}-{idx:02d}'
                DiningTable.objects.update_or_create(
                    tenant=tenant,
                    store=store,
                    code=code,
                    defaults={
                        'name': f'Bàn {idx:02d}',
                        'display_order': idx,
                        'is_active': True,
                    },
                )

        if seed_qr_pending:
            QROrder.objects.filter(tenant=tenant, status=QROrder.Status.PENDING, customer_note__startswith='[seed]').delete()
            self._seed_pending_qr_orders(tenant=tenant, store_map=store_map)

        self.stdout.write(self.style.SUCCESS('Seed dữ liệu thành công.'))
        self.stdout.write(f'Tenant: {tenant.public_slug} ({tenant.name})')
        self.stdout.write(f'Manager: {manager.username}')
        self.stdout.write(f'Staff: {", ".join(u.username for u in staff_users)}')
        self.stdout.write(f'Tổng sản phẩm seed: {len(product_ids)}')
        self.stdout.write('Bàn mỗi cửa hàng: 12')

    def _seed_pending_qr_orders(self, *, tenant, store_map):
        stores = list(store_map.values())
        for store_index, store in enumerate(stores, start=1):
            tables = list(DiningTable.objects.filter(store=store, is_active=True).order_by('display_order')[:2])
            if not tables:
                continue

            for idx, table in enumerate(tables, start=1):
                qr_order = QROrder.objects.create(
                    tenant=tenant,
                    store=store,
                    table=table,
                    status=QROrder.Status.PENDING,
                    customer_note=f'[seed] Đơn demo {store_index}-{idx}',
                )

                units = list(
                    ProductUnit.objects.filter(
                        product__tenant=tenant,
                        product__is_active=True,
                        is_active=True,
                        product__store_links__store=store,
                        product__store_links__is_available=True,
                    )
                    .select_related('product')
                    .order_by('id')[:3]
                )

                for unit_idx, unit in enumerate(units, start=1):
                    quantity = 1 + (unit_idx % 2)
                    price = get_effective_unit_price(unit=unit, store_id=store.id)
                    QROrderItem.objects.create(
                        qr_order=qr_order,
                        product=unit.product,
                        unit=unit,
                        snapshot_product_name=unit.product.name,
                        snapshot_unit_name=unit.name,
                        unit_price_snapshot=price,
                        quantity=quantity,
                        note='Ít đá' if unit_idx == 1 else '',
                        line_total=Decimal('0'),
                    )

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

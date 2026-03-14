# python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
from argparse import BooleanOptionalAction
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Sales.models import DiningTable, QROrder, QROrderItem, QROrderItemTopping
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

        # Seed gọn theo bộ sản phẩm mẫu có ảnh thật (Unsplash) giống mock POS.
        product_templates = [
            {
                'name': 'Cà phê Sữa đá',
                'category': 'Cà phê',
                'image_url': 'https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=300&q=80',
                'units': [('S', Decimal('29000')), ('M', Decimal('35000')), ('L', Decimal('39000'))],
            },
            {
                'name': 'Trà Đào Cam Sả',
                'category': 'Nước uống',
                'image_url': 'https://images.unsplash.com/photo-1499638673689-79a0b5115d87?auto=format&fit=crop&w=300&q=80',
                'units': [('M', Decimal('45000')), ('L', Decimal('55000'))],
            },
            {
                'name': 'Bạc Xỉu',
                'category': 'Cà phê',
                'image_url': 'https://images.unsplash.com/photo-1541167760496-1628856ab772?auto=format&fit=crop&w=300&q=80',
                'units': [('M', Decimal('35000')), ('L', Decimal('42000'))],
            },
            {
                'name': 'Trà Sữa Trân Châu',
                'category': 'Trà sữa',
                'image_url': 'https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=300&q=80',
                'units': [('M', Decimal('50000')), ('L', Decimal('60000'))],
            },
            {
                'name': 'Phở Bò Kobe',
                'category': 'Đồ ăn',
                'image_url': 'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?auto=format&fit=crop&w=300&q=80',
                'units': [('Thường', Decimal('85000')), ('Đặc biệt', Decimal('110000'))],
            },
            {
                'name': 'Bánh Mì Thịt Nướng',
                'category': 'Đồ ăn',
                'image_url': 'https://images.unsplash.com/photo-1509722747041-616f39b57569?auto=format&fit=crop&w=300&q=80',
                'units': [('Thường', Decimal('25000'))],
            },
            {
                'name': 'Cơm Tấm Sườn Bì',
                'category': 'Đồ ăn',
                'image_url': 'https://images.unsplash.com/photo-1623653387945-2fd25214f8fc?auto=format&fit=crop&w=300&q=80',
                'units': [('Thường', Decimal('55000')), ('Đặc biệt', Decimal('75000'))],
            },
            {
                'name': 'Gỏi Cuốn Tôm Thịt',
                'category': 'Đồ ăn',
                'image_url': 'https://images.unsplash.com/photo-1559847844-5315695dadae?auto=format&fit=crop&w=300&q=80',
                'units': [('Phần', Decimal('30000'))],
            },
            {
                'name': 'Combo Sáng Ăn Chắc',
                'category': 'Combo',
                'image_url': 'https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?auto=format&fit=crop&w=300&q=80',
                'units': [('Combo', Decimal('65000'))],
            },
            {
                'name': 'Combo Trưa Vui Vẻ',
                'category': 'Combo',
                'image_url': 'https://images.unsplash.com/photo-1615719413546-198b25453f85?auto=format&fit=crop&w=300&q=80',
                'units': [('Combo', Decimal('89000'))],
            },
        ]

        curated_product_names = {row['name'] for row in product_templates}
        Product.objects.filter(tenant=tenant).exclude(name__in=curated_product_names).update(is_active=False)

        product_counter = 0
        product_ids = []
        for row in product_templates:
            product_counter += 1
            category = category_map[row['category']]
            product_name = row['name']
            image_url = row['image_url']
            product, _ = Product.objects.get_or_create(
                tenant=tenant,
                name=product_name,
                defaults={
                    'category': category,
                    'short_description': f'{product_name} chuẩn vị',
                    'description': f'Sản phẩm {product_name}',
                    'image_url': image_url,
                    'is_active': True,
                },
            )
            product.category = category
            product.short_description = f'{product_name} chuẩn vị'
            product.description = f'Sản phẩm {product_name}'
            product.image_url = image_url
            product.is_active = True
            product.save()
            product_ids.append(product.id)

            unit_names = [unit_name for unit_name, _ in row['units']]
            ProductUnit.objects.filter(product=product).exclude(name__in=unit_names).update(is_active=False)
            for unit_order, (unit_name, unit_price) in enumerate(row['units'], start=1):
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

        topping_templates = [
            {'name': 'Thêm sữa', 'display_order': 1},
            {'name': 'Trân châu trắng', 'display_order': 2},
            {'name': 'Thạch phô mai', 'display_order': 3},
            {'name': 'Pudding trứng', 'display_order': 4},
            {'name': 'Thêm thịt', 'display_order': 5},
            {'name': 'Ốp la', 'display_order': 6},
            {'name': 'Thêm quẩy', 'display_order': 7},
            {'name': 'Trứng chần', 'display_order': 8},
            {'name': 'Chả cua', 'display_order': 9},
        ]
        curated_topping_names = {row['name'] for row in topping_templates}
        Topping.objects.filter(tenant=tenant).exclude(name__in=curated_topping_names).update(is_active=False)

        topping_map = {}
        for row in topping_templates:
            topping, _ = Topping.objects.get_or_create(
                tenant=tenant,
                name=row['name'],
                defaults={'is_active': True, 'display_order': row['display_order']},
            )
            topping.is_active = True
            topping.display_order = row['display_order']
            topping.save(update_fields=['is_active', 'display_order', 'updated_at'])
            topping_map[row['name']] = topping

        ProductTopping.objects.filter(product__tenant=tenant).update(is_active=False)
        product_topping_seed = [
            ('Trà Sữa Trân Châu', [('Trân châu trắng', Decimal('10000')), ('Thạch phô mai', Decimal('15000')), ('Pudding trứng', Decimal('12000'))]),
            ('Bạc Xỉu', [('Thêm sữa', Decimal('5000'))]),
            ('Bánh Mì Thịt Nướng', [('Thêm thịt', Decimal('10000')), ('Ốp la', Decimal('6000'))]),
            ('Phở Bò Kobe', [('Thêm quẩy', Decimal('5000')), ('Trứng chần', Decimal('8000'))]),
            ('Cơm Tấm Sườn Bì', [('Chả cua', Decimal('15000')), ('Ốp la', Decimal('6000'))]),
        ]
        for product_name, topping_rows in product_topping_seed:
            product = Product.objects.filter(tenant=tenant, name=product_name).first()
            if not product:
                continue
            for order_idx, (topping_name, topping_price) in enumerate(topping_rows, start=1):
                topping = topping_map[topping_name]
                ProductTopping.objects.update_or_create(
                    product=product,
                    topping=topping,
                    defaults={
                        'price': topping_price,
                        'display_order': order_idx,
                        'is_active': True,
                    },
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
                    qr_item = QROrderItem.objects.create(
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
                    if unit_idx == 1:
                        first_link = (
                            ProductTopping.objects.select_related('topping')
                            .filter(product=unit.product, is_active=True, topping__is_active=True)
                            .order_by('display_order', 'id')
                            .first()
                        )
                        if first_link:
                            qr_item.unit_price_snapshot = qr_item.unit_price_snapshot + first_link.price
                            qr_item.save()
                            QROrderItemTopping.objects.update_or_create(
                                qr_order_item=qr_item,
                                topping=first_link.topping,
                                defaults={
                                    'snapshot_topping_name': first_link.topping.name,
                                    'snapshot_price': first_link.price,
                                },
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

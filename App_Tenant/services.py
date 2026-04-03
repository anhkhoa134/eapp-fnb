from decimal import Decimal

from django.db import transaction
from django.utils.text import slugify

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable
from App_Tenant.models import Store, UserStoreAccess

DEFAULT_TENANT_USER_PASSWORD = '123456'


def get_user_accessible_stores(user):
    if not user.is_authenticated or not user.tenant_id:
        return Store.objects.none()
    store_ids = UserStoreAccess.objects.filter(user=user).values_list('store_id', flat=True)
    return Store.objects.filter(id__in=store_ids, is_active=True).order_by('name')


def get_default_store_for_user(user):
    if not user.is_authenticated:
        return None
    default_access = (
        UserStoreAccess.objects.select_related('store')
        .filter(user=user, is_default=True, store__is_active=True)
        .first()
    )
    if default_access:
        return default_access.store
    return get_user_accessible_stores(user).first()


def _generate_unique_username(base_username):
    base_username = (base_username or '').strip().replace('-', '_') or 'user'
    base_username = base_username[:150]
    candidate = base_username
    suffix_index = 2
    while User.objects.filter(username=candidate).exists():
        suffix = f'_{suffix_index}'
        candidate = f'{base_username[:150 - len(suffix)]}{suffix}'
        suffix_index += 1
    return candidate


def provision_tenant_owner_and_store(tenant, *, store_name='Cửa hàng trung tâm', store_address=''):
    normalized_slug = slugify(store_name) or f'store-{tenant.pk}'
    tenant_key = (tenant.public_slug or slugify(tenant.name) or f'tenant-{tenant.pk}').replace('-', '_')
    manager_username = _generate_unique_username(f'{tenant_key}_quanly')
    staff_username = _generate_unique_username(f'{tenant_key}_nhanvien_1')

    with transaction.atomic():
        store = Store.objects.create(
            tenant=tenant,
            name=store_name,
            slug=normalized_slug,
            address=store_address,
            is_active=True,
            is_default=True,
        )
        manager_user = User.objects.create_user(
            username=manager_username,
            password=DEFAULT_TENANT_USER_PASSWORD,
            tenant=tenant,
            role=User.Role.MANAGER,
            is_staff=True,
        )
        staff_user = User.objects.create_user(
            username=staff_username,
            password=DEFAULT_TENANT_USER_PASSWORD,
            tenant=tenant,
            role=User.Role.STAFF,
            is_staff=False,
        )

        UserStoreAccess.objects.create(user=manager_user, store=store, is_default=True)
        UserStoreAccess.objects.create(user=staff_user, store=store, is_default=True)

    return manager_user, staff_user, store


def provision_tenant_default_setup(tenant, *, default_password=DEFAULT_TENANT_USER_PASSWORD):
    tenant_key = (tenant.public_slug or slugify(tenant.name) or f'tenant-{tenant.pk}').replace('-', '_')
    manager_username = _generate_unique_username(f'{tenant_key}_quanly')
    staff_usernames = [
        _generate_unique_username(f'{tenant_key}_nhanvien_1'),
        _generate_unique_username(f'{tenant_key}_nhanvien_2'),
    ]

    with transaction.atomic():
        store = Store.objects.create(
            tenant=tenant,
            name='Cửa hàng trung tâm',
            address='01 Nguyễn Huệ, Q1, TP.HCM',
            is_active=True,
            is_default=True,
        )

        manager_user = User.objects.create_user(
            username=manager_username,
            password=default_password,
            tenant=tenant,
            role=User.Role.MANAGER,
            is_staff=True,
            is_active=True,
        )

        staff_users = []
        for username in staff_usernames:
            staff_users.append(
                User.objects.create_user(
                    username=username,
                    password=default_password,
                    tenant=tenant,
                    role=User.Role.STAFF,
                    is_staff=False,
                    is_active=True,
                )
            )

        for user in [manager_user, *staff_users]:
            UserStoreAccess.objects.create(user=user, store=store, is_default=True)

        for idx in range(1, 13):
            DiningTable.objects.create(
                tenant=tenant,
                store=store,
                code=f'BAN-{idx:02d}',
                name=f'Bàn {idx:02d}',
                display_order=idx,
                is_active=True,
            )

        categories = {
            'Đồ ăn': Category.objects.create(
                tenant=tenant,
                name='Đồ ăn',
                description='Danh mục món ăn cơ bản',
                is_active=True,
            ),
            'Nước uống': Category.objects.create(
                tenant=tenant,
                name='Nước uống',
                description='Danh mục thức uống cơ bản',
                is_active=True,
            ),
        }

        for category in categories.values():
            StoreCategory.objects.create(store=store, category=category, is_visible=True)

        product_seed = [
            ('Cà phê Sữa đá', 'Nước uống', 'M', Decimal('29000')),
            ('Trà Đào Cam Sả', 'Nước uống', 'M', Decimal('45000')),
            ('Bánh Mì Thịt Nướng', 'Đồ ăn', 'Phần', Decimal('25000')),
            ('Cơm Tấm Sườn Bì', 'Đồ ăn', 'Phần', Decimal('55000')),
        ]
        for product_name, category_name, unit_name, unit_price in product_seed:
            product = Product.objects.create(
                tenant=tenant,
                category=categories[category_name],
                name=product_name,
                description=f'Sản phẩm mẫu: {product_name}',
                is_active=True,
            )
            ProductUnit.objects.create(
                product=product,
                name=unit_name,
                price=unit_price,
                display_order=1,
                is_active=True,
            )
            StoreProduct.objects.create(store=store, product=product, is_available=True)

    return {
        'store': store,
        'manager_user': manager_user,
        'staff_users': staff_users,
    }

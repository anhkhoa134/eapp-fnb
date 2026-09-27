from decimal import Decimal

from django.db import transaction
from django.utils.text import slugify

from App_Accounts.models import User
from App_Catalog.models import Category, Product, ProductUnit, StoreCategory, StoreProduct
from App_Sales.models import DiningTable
from App_Tenant.models import RESERVED_PUBLIC_SLUGS, Store, SubscriptionPlan, Tenant, UserStoreAccess

DEFAULT_TENANT_USER_PASSWORD = '123456'
SIGNUP_DEFAULT_TABLE_COUNT = 5


def get_default_subscription_plan():
    return SubscriptionPlan.objects.filter(is_default=True).order_by('sort_order', 'pk').first()


def _capped(count, limit):
    return count if limit is None else min(count, limit)


def _generate_unique_public_slug(name):
    max_length = Tenant._meta.get_field('public_slug').max_length
    base_slug = slugify(name)[:max_length].strip('-') or 'cua-hang'
    candidate = base_slug
    suffix = 2
    while candidate in RESERVED_PUBLIC_SLUGS or Tenant.objects.filter(public_slug=candidate).exists():
        tail = f'-{suffix}'
        candidate = f'{base_slug[:max_length - len(tail)].rstrip("-")}{tail}'
        suffix += 1
    return candidate


def register_free_tenant(*, store_name, username, password, email=''):
    """Đăng ký tự phục vụ: tạo doanh nghiệp (gói mặc định), 1 cửa hàng, 1 tài khoản quản lý và vài bàn."""
    store_name = store_name.strip()
    with transaction.atomic():
        tenant = Tenant(name=store_name, public_slug=_generate_unique_public_slug(store_name))
        tenant.apply_subscription_plan(get_default_subscription_plan())
        tenant.save()

        store = Store.objects.create(tenant=tenant, name=store_name, is_active=True, is_default=True)
        manager_user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            tenant=tenant,
            role=User.Role.MANAGER,
            is_staff=False,
        )
        UserStoreAccess.objects.create(user=manager_user, store=store, is_default=True)

        for idx in range(1, _capped(SIGNUP_DEFAULT_TABLE_COUNT, tenant.max_dining_tables) + 1):
            DiningTable.objects.create(
                tenant=tenant,
                store=store,
                code=f'BAN-{idx:02d}',
                name=f'Bàn {idx:02d}',
                display_order=idx,
                is_active=True,
            )

    return manager_user


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
        _generate_unique_username(f'{tenant_key}_nhanvien_{idx}')
        for idx in range(1, _capped(2, tenant.max_staff_users) + 1)
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

        for idx in range(1, _capped(12, tenant.max_dining_tables) + 1):
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
        for product_name, category_name, unit_name, unit_price in product_seed[: _capped(len(product_seed), tenant.max_products)]:
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

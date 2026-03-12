from django.db import transaction
from django.utils.text import slugify

from App_Accounts.models import User
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

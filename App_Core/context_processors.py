from App_Tenant.services import get_default_store_for_user, get_user_accessible_stores


def core_context(request):
    account_stores = []
    account_default_store_id = None
    if request.user.is_authenticated:
        account_stores = list(get_user_accessible_stores(request.user))
        default_store = get_default_store_for_user(request.user)
        account_default_store_id = default_store.id if default_store else None

    return {
        'app_name': 'eApp FnB',
        'account_stores': account_stores,
        'account_default_store_id': account_default_store_id,
    }

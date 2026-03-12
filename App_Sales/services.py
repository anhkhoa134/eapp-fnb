from decimal import Decimal

from App_Catalog.models import ProductUnit, StoreProduct
from App_Tenant.services import get_default_store_for_user, get_user_accessible_stores


def get_accessible_store_or_default(user, store_id=None):
    stores = get_user_accessible_stores(user)
    if store_id:
        return stores.filter(id=store_id).first()
    return get_default_store_for_user(user)


def get_effective_unit_price(*, unit: ProductUnit, store_id: int) -> Decimal:
    link = StoreProduct.objects.filter(store_id=store_id, product=unit.product, is_available=True).first()
    if link and link.custom_price is not None:
        return link.custom_price
    return unit.price

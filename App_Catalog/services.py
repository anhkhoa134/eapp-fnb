from decimal import Decimal

from App_Catalog.models import Product, ProductTopping


def parse_topping_ids(raw_topping_ids):
    if raw_topping_ids in (None, ''):
        return []
    if not isinstance(raw_topping_ids, list):
        raise ValueError('topping_ids phải là danh sách.')

    normalized = []
    seen = set()
    for raw_id in raw_topping_ids:
        try:
            topping_id = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError('topping_ids chứa giá trị không hợp lệ.')
        if topping_id <= 0:
            raise ValueError('topping_ids chứa giá trị không hợp lệ.')
        if topping_id in seen:
            continue
        seen.add(topping_id)
        normalized.append(topping_id)
    return normalized


def resolve_product_topping_links(*, product: Product, topping_ids):
    topping_ids = parse_topping_ids(topping_ids)
    if not topping_ids:
        return []

    links = list(
        ProductTopping.objects.select_related('topping').filter(
            product=product,
            topping_id__in=topping_ids,
            is_active=True,
            topping__is_active=True,
            topping__tenant_id=product.tenant_id,
        )
    )
    if len(links) != len(topping_ids):
        raise ValueError('Topping không hợp lệ cho sản phẩm đã chọn.')
    return links


def calc_toppings_total(links):
    total = Decimal('0')
    for link in links:
        total += link.price
    return total


def serialize_topping_links(links):
    return [
        {
            'id': link.topping_id,
            'name': link.topping.name,
            'price': float(link.price),
        }
        for link in sorted(links, key=lambda row: (row.display_order, row.id))
    ]


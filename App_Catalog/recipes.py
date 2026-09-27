"""Định mức nguyên liệu: lưu định mức cho thành phẩm, tính giá vốn và tiêu hao theo đơn bán."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from App_Catalog.models import Ingredient, RecipeItem

ZERO = Decimal('0')
MAX_RECIPE_QUANTITY = Decimal('999999999.999')


def recipe_enabled(tenant) -> bool:
    return bool(tenant and tenant.recipe_feature_enabled)


def recipe_cost(recipe_items) -> Decimal:
    """Giá vốn 1 thành phẩm = tổng (định mức x giá vốn / đơn vị nguyên liệu)."""
    return sum((item.cost for item in recipe_items), ZERO)


def parse_recipe_rows(ingredient_ids, quantities):
    """Ghép 2 danh sách POST thành [(ingredient_id, quantity)], bỏ dòng trống hoàn toàn."""
    rows = []
    if len(ingredient_ids) != len(quantities):
        raise ValidationError('Mỗi dòng định mức phải có đủ nguyên liệu và số lượng.')
    for raw_id, raw_qty in zip(ingredient_ids, quantities):
        raw_id = (raw_id or '').strip()
        raw_qty = (raw_qty or '').strip().replace(',', '.')
        if not raw_id and not raw_qty:
            continue
        if not raw_id.isascii() or not raw_id.isdigit() or len(raw_id) > 19 or int(raw_id) > 9223372036854775807:
            raise ValidationError('Vui lòng chọn nguyên liệu cho từng dòng định mức.')
        try:
            quantity = Decimal(raw_qty)
        except InvalidOperation:
            raise ValidationError('Định mức phải là số.')
        if not quantity.is_finite() or quantity <= 0:
            raise ValidationError('Định mức phải lớn hơn 0.')
        if quantity > MAX_RECIPE_QUANTITY:
            raise ValidationError('Định mức quá lớn.')
        rounded = quantity.quantize(Decimal('0.001'))
        if rounded != quantity:
            raise ValidationError('Định mức chỉ được có tối đa 3 chữ số thập phân.')
        rows.append((int(raw_id), rounded))
    return rows


def save_recipe(*, tenant, rows, product_unit=None, topping=None):
    """Thay toàn bộ định mức của 1 thành phẩm (đơn vị bán hoặc topping) bằng `rows`."""
    if (product_unit is None) == (topping is None):
        raise ValueError('Cần đúng 1 thành phẩm: product_unit hoặc topping.')
    target_tenant_id = product_unit.product.tenant_id if product_unit is not None else topping.tenant_id
    if target_tenant_id != tenant.pk:
        raise ValidationError('Thành phẩm không thuộc doanh nghiệp hiện tại.')
    ingredient_ids = [ingredient_id for ingredient_id, _qty in rows]
    if len(ingredient_ids) != len(set(ingredient_ids)):
        raise ValidationError('Mỗi nguyên liệu chỉ được khai báo 1 lần trong định mức.')
    ingredients = Ingredient.objects.filter(tenant=tenant, pk__in=ingredient_ids).in_bulk()
    if len(ingredients) != len(ingredient_ids):
        raise ValidationError('Có nguyên liệu không thuộc doanh nghiệp hiện tại.')

    target = {'product_unit': product_unit} if product_unit is not None else {'topping': topping}
    items = []
    for ingredient_id, qty in rows:
        quantity = RecipeItem._meta.get_field('quantity').clean(qty, None)
        item = RecipeItem(ingredient=ingredients[ingredient_id], quantity=quantity, **target)
        item.clean()
        items.append(item)
    with transaction.atomic():
        # Khoá thành phẩm để hai lần lưu đồng thời không trộn các dòng định mức.
        target_obj = product_unit if product_unit is not None else topping
        type(target_obj).objects.select_for_update().get(pk=target_obj.pk)
        RecipeItem.objects.filter(**target).delete()
        RecipeItem.objects.bulk_create(items)


def _recipes_by(field, target_ids):
    recipes = defaultdict(list)
    items = RecipeItem.objects.filter(**{f'{field}__in': target_ids}).select_related('ingredient')
    for item in items:
        recipes[getattr(item, f'{field}_id')].append(item)
    return recipes


def compute_ingredient_usage(order_items):
    """
    Tiêu hao nguyên liệu lý thuyết cho `order_items` (queryset OrderItem), theo định mức hiện tại.
    Topping tính theo số lượng món chứa topping đó.
    """
    from App_Sales.models import OrderItemTopping

    unit_sales = list(
        order_items.order_by()
        .values('unit_id', 'snapshot_product_name', 'snapshot_unit_name')
        .annotate(sold=Sum('quantity'))
    )
    topping_sales = list(
        OrderItemTopping.objects.filter(order_item__in=order_items)
        .order_by()
        .values('topping_id', 'snapshot_topping_name')
        .annotate(sold=Sum('order_item__quantity'))
    )
    unit_recipes = _recipes_by('product_unit', {row['unit_id'] for row in unit_sales if row['unit_id']})
    topping_recipes = _recipes_by('topping', {row['topping_id'] for row in topping_sales if row['topping_id']})

    usage = {}
    missing = []

    def consume(recipe_items, sold):
        for item in recipe_items:
            row = usage.setdefault(item.ingredient_id, {'ingredient': item.ingredient, 'quantity': ZERO})
            row['quantity'] += item.quantity * sold

    for row in unit_sales:
        recipe_items = unit_recipes.get(row['unit_id'])
        if recipe_items:
            consume(recipe_items, row['sold'])
        else:
            missing.append(
                {'name': f"{row['snapshot_product_name']} - {row['snapshot_unit_name']}", 'sold': row['sold']}
            )
    for row in topping_sales:
        recipe_items = topping_recipes.get(row['topping_id'])
        if recipe_items:
            consume(recipe_items, row['sold'])
        else:
            missing.append({'name': f"Topping {row['snapshot_topping_name']}", 'sold': row['sold']})

    rows = sorted(usage.values(), key=lambda r: (r['ingredient'].display_order, r['ingredient'].name))
    for row in rows:
        row['cost'] = row['quantity'] * row['ingredient'].cost_per_unit
    missing.sort(key=lambda r: (-r['sold'], r['name']))
    return {
        'rows': rows,
        'total_cost': sum((row['cost'] for row in rows), ZERO),
        'missing': missing,
    }

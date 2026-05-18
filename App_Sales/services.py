from decimal import Decimal

from django.db.models import Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from App_Catalog.models import ProductUnit, StoreProduct
from App_Sales.models import Customer, Order, Promotion
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


LOYALTY_POINT_STEP = Decimal('10000')


def get_customer_tier(total_spent: Decimal) -> str:
    total_spent = total_spent or Decimal('0')
    if total_spent >= Decimal('50000000'):
        return Customer.Tier.VIP
    if total_spent >= Decimal('20000000'):
        return Customer.Tier.GOLD
    if total_spent >= Decimal('5000000'):
        return Customer.Tier.SILVER
    return Customer.Tier.MEMBER


def calculate_points_for_amount(amount: Decimal) -> int:
    amount = amount or Decimal('0')
    if amount <= 0:
        return 0
    return int(amount // LOYALTY_POINT_STEP)


def recompute_customer_stats(customer: Customer):
    if not customer:
        return None
    stats = Order.objects.filter(
        customer=customer,
        tenant=customer.tenant,
        status=Order.Status.COMPLETED,
    ).aggregate(
        total_spent=Coalesce(Sum('total_amount'), Decimal('0')),
        last_order_at=Max('created_at'),
    )
    total_spent = stats['total_spent'] or Decimal('0')
    customer.total_spent = total_spent
    customer.points_balance = calculate_points_for_amount(total_spent)
    customer.tier = get_customer_tier(total_spent)
    customer.last_order_at = stats['last_order_at']
    customer.save(update_fields=['total_spent', 'points_balance', 'tier', 'last_order_at', 'updated_at'])
    return customer


def get_available_promotions(*, tenant, store, subtotal: Decimal, at=None):
    at = at or timezone.now()
    subtotal = subtotal or Decimal('0')
    return (
        Promotion.objects.filter(tenant=tenant, is_active=True, min_order_amount__lte=subtotal)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=at))
        .filter(Q(stores__isnull=True) | Q(stores=store))
        .distinct()
        .order_by('name', 'id')
    )


def calculate_promotion_discount(*, promotion: Promotion | None, subtotal: Decimal) -> Decimal:
    subtotal = subtotal or Decimal('0')
    if not promotion or subtotal <= 0 or subtotal < promotion.min_order_amount:
        return Decimal('0')
    if promotion.discount_type == Promotion.DiscountType.PERCENT:
        discount = subtotal * (promotion.discount_value / Decimal('100'))
    else:
        discount = promotion.discount_value
    if promotion.max_discount_amount is not None:
        discount = min(discount, promotion.max_discount_amount)
    return max(Decimal('0'), min(discount, subtotal))


def calculate_order_totals(*, subtotal: Decimal, tax_rate: Decimal, promotion: Promotion | None = None):
    discount_amount = calculate_promotion_discount(promotion=promotion, subtotal=subtotal)
    taxable_amount = max(Decimal('0'), subtotal - discount_amount)
    tax_amount = taxable_amount * tax_rate
    total_amount = taxable_amount + tax_amount
    return {
        'discount_amount': discount_amount,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
    }


def resolve_customer_for_checkout(*, tenant, customer_id):
    if not customer_id:
        return None
    try:
        return Customer.objects.get(pk=customer_id, tenant=tenant, is_active=True)
    except Customer.DoesNotExist:
        return None


def resolve_promotion_for_checkout(*, tenant, store, promotion_id, subtotal: Decimal):
    if not promotion_id:
        return None
    return get_available_promotions(tenant=tenant, store=store, subtotal=subtotal).filter(pk=promotion_id).first()
